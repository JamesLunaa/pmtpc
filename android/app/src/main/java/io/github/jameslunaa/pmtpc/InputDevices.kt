package io.github.jameslunaa.pmtpc

import android.media.AudioDeviceCallback
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.os.Build
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext

/** A microphone the user can pick. [key] survives replugging; [id] is only valid while it stays connected. */
data class InputDevice(val id: Int, val key: String, val label: String)

// Bluetooth inputs are left out: classic headsets only offer call-quality (8-16 kHz) audio.
private val SUPPORTED_TYPES = setOf(
    AudioDeviceInfo.TYPE_BUILTIN_MIC,
    AudioDeviceInfo.TYPE_USB_DEVICE,
    AudioDeviceInfo.TYPE_USB_HEADSET,
    AudioDeviceInfo.TYPE_USB_ACCESSORY,
    AudioDeviceInfo.TYPE_WIRED_HEADSET,
)

fun AudioManager.inputDevices(): List<InputDevice> =
    getDevices(AudioManager.GET_DEVICES_INPUTS)
        .filter { it.type in SUPPORTED_TYPES }
        .map { InputDevice(it.id, "${it.type}:${it.productName}:${it.addressCompat}", it.label) }

fun AudioManager.findInput(id: Int): AudioDeviceInfo? =
    getDevices(AudioManager.GET_DEVICES_INPUTS).firstOrNull { it.id == id }

val AudioDeviceInfo.label: String
    get() = when (type) {
        AudioDeviceInfo.TYPE_BUILTIN_MIC ->
            addressCompat.takeIf { it.isNotBlank() }?.let { "Phone microphone ($it)" } ?: "Phone microphone"
        AudioDeviceInfo.TYPE_WIRED_HEADSET -> "Wired headset mic"
        else -> productName?.toString()?.takeIf { it.isNotBlank() } ?: "USB microphone"
    }

private val AudioDeviceInfo.addressCompat: String
    get() = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) address.orEmpty() else ""

/** Input devices, kept up to date as mics are plugged in and out. */
@Composable
fun rememberInputDevices(): List<InputDevice> {
    val context = LocalContext.current
    val audio = remember { context.getSystemService(AudioManager::class.java) }
    var devices by remember { mutableStateOf(audio.inputDevices()) }
    DisposableEffect(audio) {
        val callback = object : AudioDeviceCallback() {
            override fun onAudioDevicesAdded(added: Array<out AudioDeviceInfo>) {
                devices = audio.inputDevices()
            }

            override fun onAudioDevicesRemoved(removed: Array<out AudioDeviceInfo>) {
                devices = audio.inputDevices()
            }
        }
        audio.registerAudioDeviceCallback(callback, null)
        onDispose { audio.unregisterAudioDeviceCallback(callback) }
    }
    return devices
}
