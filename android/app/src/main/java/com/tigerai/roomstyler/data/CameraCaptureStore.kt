package com.tigerai.roomstyler.data

import android.content.Context
import android.net.Uri
import androidx.core.content.FileProvider
import java.io.File

object CameraCaptureStore {
    private const val DIRECTORY = "room_capture"
    private const val PREFIX = "room_"

    fun create(context: Context): Pair<File, Uri> {
        val directory = File(context.cacheDir, DIRECTORY).apply { mkdirs() }
        val file = File.createTempFile(PREFIX, ".jpg", directory)
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        return file to uri
    }

    fun uriFor(context: Context, file: File): Uri =
        FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)

    fun delete(file: File?) {
        if (file != null && file.exists()) file.delete()
    }

    fun cleanup(context: Context, keepPath: String? = null) {
        val directory = File(context.cacheDir, DIRECTORY)
        directory.listFiles()?.forEach { file ->
            if (file.isFile && file.name.startsWith(PREFIX) && file.absolutePath != keepPath) file.delete()
        }
    }
}
