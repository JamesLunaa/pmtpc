package io.github.jameslunaa.pmtpc

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.core.content.edit
import androidx.lifecycle.compose.collectAsStateWithLifecycle

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            AppTheme {
                Surface(Modifier.fillMaxSize()) {
                    MainScreen()
                }
            }
        }
    }
}

@Composable
private fun AppTheme(content: @Composable () -> Unit) {
    val context = LocalContext.current
    val dark = isSystemInDarkTheme()
    val colors = when {
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            if (dark) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        dark -> darkColorScheme()
        else -> lightColorScheme()
    }
    MaterialTheme(colorScheme = colors, content = content)
}

@Composable
private fun MainScreen() {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences("settings", Context.MODE_PRIVATE) }
    var host by rememberSaveable { mutableStateOf(prefs.getString("host", "").orEmpty()) }
    var port by rememberSaveable { mutableStateOf(prefs.getInt("port", Protocol.DEFAULT_PORT).toString()) }
    var source by rememberSaveable {
        mutableStateOf(
            prefs.getString("source", null)
                ?.let { runCatching { MicSource.valueOf(it) }.getOrNull() }
                ?: MicSource.STANDARD,
        )
    }
    var deviceKey by rememberSaveable { mutableStateOf(prefs.getString("device", null)) }
    val devices = rememberInputDevices()
    val device = devices.firstOrNull { it.key == deviceKey }
    var permissionDenied by remember { mutableStateOf(false) }
    val state by MicStreamService.state.collectAsStateWithLifecycle()
    val streaming = state is StreamState.Streaming

    val portNumber = port.toIntOrNull()?.takeIf { it in 1..65535 }
    val valid = host.isNotBlank() && portNumber != null

    fun start() {
        prefs.edit {
            putString("host", host.trim())
            putInt("port", portNumber!!)
            putString("source", source.name)
            putString("device", deviceKey)
        }
        MicStreamService.start(context, host.trim(), portNumber!!, source, device?.id)
    }

    val permissions = buildList {
        add(Manifest.permission.RECORD_AUDIO)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) add(Manifest.permission.POST_NOTIFICATIONS)
    }.toTypedArray()
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { results ->
        // Notifications are optional; the microphone is not.
        permissionDenied = results[Manifest.permission.RECORD_AUDIO] != true
        if (!permissionDenied) start()
    }

    Column(
        Modifier
            .verticalScroll(rememberScrollState())
            .safeDrawingPadding()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text("Phone Mic to PC", style = MaterialTheme.typography.headlineMedium)

        OutlinedTextField(
            value = host,
            onValueChange = { host = it },
            label = { Text("PC IP address") },
            placeholder = { Text("192.168.1.50") },
            singleLine = true,
            enabled = !streaming,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = port,
            onValueChange = { port = it.filter(Char::isDigit).take(5) },
            label = { Text("Port") },
            singleLine = true,
            enabled = !streaming,
            isError = portNumber == null,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            modifier = Modifier.fillMaxWidth(),
        )

        Text("Microphone", style = MaterialTheme.typography.titleMedium)
        OptionList(
            options = listOf<InputDevice?>(null) + devices,
            selected = device,
            enabled = !streaming,
            label = { it?.label ?: "Automatic" },
            description = { if (it == null) "Let Android choose (usually a plugged-in mic)" else null },
            onSelect = { deviceKey = it?.key },
        )

        Text("Microphone mode", style = MaterialTheme.typography.titleMedium)
        OptionList(
            options = MicSource.entries,
            selected = source,
            enabled = !streaming,
            label = { it.label },
            description = { it.description },
            onSelect = { source = it },
        )

        Button(
            onClick = {
                when {
                    streaming -> MicStreamService.stop(context)
                    ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
                        PackageManager.PERMISSION_GRANTED -> start()
                    else -> permissionLauncher.launch(permissions)
                }
            },
            enabled = streaming || valid,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(if (streaming) "Stop" else "Start")
        }

        StatusText(state, permissionDenied)
    }
}

@Composable
private fun <T> OptionList(
    options: List<T>,
    selected: T,
    enabled: Boolean,
    label: (T) -> String,
    description: (T) -> String?,
    onSelect: (T) -> Unit,
) {
    Column(Modifier.selectableGroup()) {
        options.forEach { option ->
            Row(
                Modifier
                    .fillMaxWidth()
                    .selectable(
                        selected = option == selected,
                        enabled = enabled,
                        role = Role.RadioButton,
                        onClick = { onSelect(option) },
                    )
                    .padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RadioButton(selected = option == selected, onClick = null, enabled = enabled)
                Column(Modifier.padding(start = 12.dp)) {
                    Text(label(option), style = MaterialTheme.typography.bodyLarge)
                    description(option)?.let {
                        Text(
                            it,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun StatusText(state: StreamState, permissionDenied: Boolean) {
    val (text, isError) = when {
        permissionDenied && state !is StreamState.Streaming ->
            "Microphone permission is required to stream." to true
        state is StreamState.Streaming -> buildString {
            append("Streaming to ${state.host}:${state.port}")
            state.input?.let { append("\nRecording from: $it") }
            append("\n${state.packetsSent} packets sent")
            if (state.sendErrors > 0) append(", ${state.sendErrors} send errors")
        } to false
        state is StreamState.Failed -> "Error: ${state.message}" to true
        else -> "Not streaming" to false
    }
    Text(
        text,
        style = MaterialTheme.typography.bodyMedium,
        color = if (isError) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
    )
}
