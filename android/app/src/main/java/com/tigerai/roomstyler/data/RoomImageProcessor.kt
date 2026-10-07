package com.tigerai.roomstyler.data

import android.content.ContentResolver
import android.graphics.Bitmap
import android.graphics.ImageDecoder
import android.net.Uri
import android.provider.OpenableColumns
import com.tigerai.roomstyler.model.ProcessedRoomImage
import com.tigerai.roomstyler.model.UserFacingException
import java.io.ByteArrayOutputStream
import kotlin.math.roundToInt

object RoomImageProcessor {
    private const val MAX_UPLOAD_BYTES = 10L * 1024L * 1024L
    private const val MAX_PIXELS = 25_000_000L
    private const val PROVIDER_LONGEST_EDGE = 2048

    fun process(resolver: ContentResolver, uri: Uri): ProcessedRoomImage {
        val type = resolver.getType(uri)?.lowercase()
        if (type !in setOf("image/jpeg", "image/png", "image/webp")) {
            throw UserFacingException("僅支援 JPEG、PNG 或 WebP 圖片。")
        }
        resolver.openFileDescriptor(uri, "r")?.use { descriptor ->
            val size = descriptor.statSize
            if (size > MAX_UPLOAD_BYTES) throw UserFacingException("圖片檔案不可超過 10 MiB。")
        } ?: throw UserFacingException("無法讀取所選照片。")

        var originalWidth = 0
        var originalHeight = 0
        val bitmap = try {
            ImageDecoder.decodeBitmap(ImageDecoder.createSource(resolver, uri)) { decoder, info, _ ->
                originalWidth = info.size.width
                originalHeight = info.size.height
                if (originalWidth <= 0 || originalHeight <= 0 ||
                    originalWidth.toLong() * originalHeight.toLong() > MAX_PIXELS
                ) {
                    throw UserFacingException("圖片解碼後不可超過 25,000,000 像素。")
                }
                val longest = maxOf(originalWidth, originalHeight)
                if (longest > PROVIDER_LONGEST_EDGE) {
                    val scale = PROVIDER_LONGEST_EDGE.toFloat() / longest.toFloat()
                    decoder.setTargetSize(
                        (originalWidth * scale).roundToInt().coerceAtLeast(1),
                        (originalHeight * scale).roundToInt().coerceAtLeast(1)
                    )
                }
                decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
                decoder.isMutableRequired = false
            }
        } catch (error: UserFacingException) {
            throw error
        } catch (_: Exception) {
            throw UserFacingException("圖片已損毀、格式不受支援，或內容無法解碼。")
        }

        val output = ByteArrayOutputStream()
        if (!bitmap.compress(Bitmap.CompressFormat.JPEG, 90, output)) {
            bitmap.recycle()
            throw UserFacingException("無法準備供雲端分析使用的圖片。")
        }
        val bytes = output.toByteArray()
        if (bytes.isEmpty() || bytes.size > MAX_UPLOAD_BYTES) {
            bitmap.recycle()
            throw UserFacingException("處理後圖片大小無效。")
        }
        return ProcessedRoomImage(
            bitmap = bitmap,
            jpegBytes = bytes,
            width = bitmap.width,
            height = bitmap.height,
            resized = maxOf(originalWidth, originalHeight) > PROVIDER_LONGEST_EDGE,
            sourceName = queryName(resolver, uri)
        )
    }

    private fun queryName(resolver: ContentResolver, uri: Uri): String {
        return try {
            resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) cursor.getString(0) ?: "room-photo" else "room-photo"
            } ?: "room-photo"
        } catch (_: Exception) {
            "room-photo"
        }
    }
}
