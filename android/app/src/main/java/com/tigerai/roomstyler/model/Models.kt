package com.tigerai.roomstyler.model

import android.graphics.Bitmap

enum class ProviderModel(val displayName: String, val modelId: String) {
    NVIDIA("NVIDIA NIM — z-ai/glm-5.3-flash", "z-ai/glm-5.3-flash"),
    OPENAI("OpenAI — gpt-image-2.5-sunburst", "gpt-image-2.5-sunburst")
}

enum class MainGoal(val wireValue: String, val label: String) {
    ORGANIZATION("organization", "改善整理"),
    AESTHETICS("aesthetics", "改善視覺感受"),
    BOTH("both", "兩者兼顧")
}

enum class StylePreference(val wireValue: String, val label: String) {
    SIMPLE("simple_and_clean", "簡潔清爽"),
    WARM("warm_and_natural", "溫暖自然"),
    PRESERVE("preserve_current_style", "保留目前風格")
}

enum class Priority(val wireValue: String, val label: String, val rank: Int) {
    HIGH("high", "高優先", 0), MEDIUM("medium", "中優先", 1), LOW("low", "低優先", 2)
}

enum class CompletionState(val label: String) {
    PENDING("未處理"), COMPLETED("已完成"), SKIPPED("暫不處理")
}

data class AnalysisConstraints(
    val mainGoal: MainGoal = MainGoal.BOTH,
    val style: StylePreference = StylePreference.PRESERVE,
    val allowMovingLargeFurniture: Boolean = false,
    val allowPurchases: Boolean = false,
    val preserveItems: String = "",
    val additionalConstraints: String = ""
)

data class ProcessedRoomImage(
    val bitmap: Bitmap,
    val jpegBytes: ByteArray,
    val width: Int,
    val height: Int,
    val resized: Boolean,
    val sourceName: String
)

data class BoundingBox(val xMin: Float, val yMin: Float, val xMax: Float, val yMax: Float)

data class InputSuitability(val suitable: Boolean, val explanation: String)

data class Observation(
    val observationId: String,
    val visibleItemOrArea: String,
    val positionDescription: String,
    val visibleEvidence: String,
    val uncertain: Boolean,
    val approximateBbox: BoundingBox?
)

data class Recommendation(
    val recommendationId: String,
    val priority: Priority,
    val supportingObservationIds: List<String>,
    val targetItemOrArea: String,
    val action: String,
    val destinationOrArrangement: String?,
    val practicalReason: String,
    val aestheticRationale: String?,
    val requiresPurchase: Boolean,
    val movesLargeFurniture: Boolean,
    val requiresConfirmation: Boolean,
    val confirmationNeeded: String?,
    val destinationObservationId: String?,
    val visualActionAvailable: Boolean,
    val visualActionNote: String?,
    val requiresExistingMaterials: Boolean,
    val noPurchaseAlternative: String?
)

data class RoomAnalysis(
    val inputSuitability: InputSuitability,
    val roomSummary: String,
    val observations: List<Observation>,
    val recommendations: List<Recommendation>,
    val uncertainties: List<String>,
    val limitations: List<String>
)

data class AnalysisSnapshot(
    val imageVersion: Long,
    val constraints: AnalysisConstraints,
    val analysis: RoomAnalysis
)

class UserFacingException(message: String) : Exception(message)
