package com.tigerai.roomstyler

import android.graphics.Paint
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.tigerai.roomstyler.data.RoomImageProcessor
import com.tigerai.roomstyler.data.CameraCaptureStore
import com.tigerai.roomstyler.model.AnalysisConstraints
import com.tigerai.roomstyler.model.AnalysisSnapshot
import com.tigerai.roomstyler.model.BoundingBox
import com.tigerai.roomstyler.model.CompletionState
import com.tigerai.roomstyler.model.MainGoal
import com.tigerai.roomstyler.model.Observation
import com.tigerai.roomstyler.model.Priority
import com.tigerai.roomstyler.model.ProcessedRoomImage
import com.tigerai.roomstyler.model.ProviderModel
import com.tigerai.roomstyler.model.Recommendation
import com.tigerai.roomstyler.model.RoomAnalysis
import com.tigerai.roomstyler.model.StylePreference
import com.tigerai.roomstyler.model.UserFacingException
import com.tigerai.roomstyler.network.NvidiaNimClient
import com.tigerai.roomstyler.network.OpenAIImageEditClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin

private val RoomGreen = Color(0xFF315C48)
private val RoomBackground = Color(0xFFF3F5EF)
private val WarningBackground = Color(0xFFFFF3DD)
private val ErrorBackground = Color(0xFFFFEDEE)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(
                colorScheme = lightColorScheme(
                    primary = RoomGreen,
                    secondary = Color(0xFFC77723),
                    background = RoomBackground,
                    surface = Color.White,
                    error = Color(0xFF9E3434)
                )
            ) {
                RoomStylerApp()
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RoomStylerApp() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var selectedModel by remember { mutableStateOf(ProviderModel.NVIDIA) }
    var apiKey by remember { mutableStateOf("") }
    var goal by remember { mutableStateOf(MainGoal.BOTH) }
    var style by remember { mutableStateOf(StylePreference.PRESERVE) }
    var allowPurchases by remember { mutableStateOf(false) }
    var allowFurnitureMovement by remember { mutableStateOf(false) }
    var preserveItems by remember { mutableStateOf("") }
    var extraConstraints by remember { mutableStateOf("") }
    var roomImage by remember { mutableStateOf<ProcessedRoomImage?>(null) }
    var imageVersion by remember { mutableLongStateOf(0L) }
    var analysisSnapshot by remember { mutableStateOf<AnalysisSnapshot?>(null) }
    val completion = remember { mutableStateMapOf<String, CompletionState>() }
    var generatedPreview by remember { mutableStateOf<android.graphics.Bitmap?>(null) }
    var busy by remember { mutableStateOf(false) }
    var busyLabel by remember { mutableStateOf("") }
    var elapsedSeconds by remember { mutableIntStateOf(0) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var pendingCapturePath by rememberSaveable { mutableStateOf<String?>(null) }

    val constraints = AnalysisConstraints(
        mainGoal = goal,
        style = style,
        allowMovingLargeFurniture = allowFurnitureMovement,
        allowPurchases = allowPurchases,
        preserveItems = preserveItems,
        additionalConstraints = extraConstraints
    )
    val previewContextCurrent = analysisSnapshot?.let {
        it.imageVersion == imageVersion && it.constraints == constraints &&
            it.analysis.inputSuitability.suitable && it.analysis.recommendations.isNotEmpty()
    } == true

    LaunchedEffect(busy) {
        if (busy) {
            elapsedSeconds = 0
            while (true) {
                delay(1_000)
                elapsedSeconds += 1
            }
        }
    }

    LaunchedEffect(Unit) {
        CameraCaptureStore.cleanup(context, pendingCapturePath)
    }

    fun processSelectedImage(uri: Uri, temporaryFile: File? = null) {
        if (busy) {
            CameraCaptureStore.delete(temporaryFile)
            return
        }
        scope.launch {
            errorMessage = null
            busy = true
            busyLabel = "正在驗證並校正照片"
            try {
                val processed = withContext(Dispatchers.IO) {
                    RoomImageProcessor.process(context.contentResolver, uri)
                }
                imageVersion += 1
                roomImage?.bitmap?.takeIf { it !== processed.bitmap }?.recycle()
                roomImage = processed
                analysisSnapshot = null
                completion.clear()
                generatedPreview?.recycle()
                generatedPreview = null
            } catch (error: UserFacingException) {
                errorMessage = error.message
            } finally {
                withContext(Dispatchers.IO) { CameraCaptureStore.delete(temporaryFile) }
                busy = false
            }
        }
    }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri != null) processSelectedImage(uri)
    }

    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { captured ->
        val file = pendingCapturePath?.let(::File)
        pendingCapturePath = null
        if (captured && file != null && file.exists()) {
            processSelectedImage(CameraCaptureStore.uriFor(context, file), file)
        } else {
            CameraCaptureStore.delete(file)
        }
    }

    fun runAnalysis() {
        val image = roomImage
        if (busy) return
        if (selectedModel != ProviderModel.NVIDIA) {
            errorMessage = "房間分析請先選擇 NVIDIA NIM — z-ai/glm-5.3-flash。"
            return
        }
        if (apiKey.isBlank()) {
            errorMessage = "請輸入目前 NVIDIA 模型使用的 API_KEY。"
            return
        }
        if (image == null) {
            errorMessage = "請先選擇一張房間照片。"
            return
        }
        val requestVersion = imageVersion
        val requestConstraints = constraints
        val requestKey = apiKey
        scope.launch {
            errorMessage = null
            generatedPreview?.recycle()
            generatedPreview = null
            busy = true
            busyLabel = "正在分析照片"
            try {
                val result = withContext(Dispatchers.IO) {
                    NvidiaNimClient.analyze(image.jpegBytes, requestKey, requestConstraints)
                }
                if (requestVersion == imageVersion) {
                    analysisSnapshot = AnalysisSnapshot(requestVersion, requestConstraints, result)
                    completion.clear()
                    result.recommendations.forEach { completion[it.recommendationId] = CompletionState.PENDING }
                }
            } catch (error: UserFacingException) {
                if (requestVersion == imageVersion) errorMessage = error.message
            } finally {
                busy = false
            }
        }
    }

    fun runPreview() {
        val image = roomImage
        val snapshot = analysisSnapshot
        if (busy) return
        if (selectedModel != ProviderModel.OPENAI) {
            errorMessage = "產生預覽請選擇 OpenAI — gpt-image-2.5-sunburst。"
            return
        }
        if (apiKey.isBlank()) {
            errorMessage = "請輸入目前 OpenAI 模型使用的 API_KEY。"
            return
        }
        if (image == null || snapshot == null || !previewContextCurrent) {
            errorMessage = "照片或限制已變更，請先以 NVIDIA 重新完成房間分析。"
            return
        }
        val requestVersion = imageVersion
        val requestKey = apiKey
        scope.launch {
            errorMessage = null
            busy = true
            busyLabel = "正在產生 AI 整理預覽"
            try {
                val result = withContext(Dispatchers.IO) {
                    OpenAIImageEditClient.edit(image.jpegBytes, requestKey, snapshot.analysis, snapshot.constraints)
                }
                if (requestVersion == imageVersion && analysisSnapshot === snapshot && constraints == snapshot.constraints) {
                    generatedPreview?.recycle()
                    generatedPreview = result
                } else {
                    result.recycle()
                }
            } catch (error: UserFacingException) {
                if (requestVersion == imageVersion) errorMessage = error.message
            } finally {
                busy = false
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Column { Text("Tiger AI RoomStyler", fontWeight = FontWeight.Bold); Text("Android MVP", fontSize = 12.sp) } },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.White)
            )
        },
        containerColor = RoomBackground
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            item {
                SectionCard("模型與金鑰") {
                    ChoiceDropdown(
                        label = "選擇模型",
                        selected = selectedModel.displayName,
                        values = ProviderModel.entries.map { it.displayName },
                        enabled = !busy,
                        onSelect = { selected ->
                            selectedModel = ProviderModel.entries.first { it.displayName == selected }
                            apiKey = ""
                            errorMessage = null
                        }
                    )
                    OutlinedTextField(
                        value = apiKey,
                        onValueChange = { apiKey = it },
                        label = { Text("API_KEY") },
                        visualTransformation = PasswordVisualTransformation(),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                        singleLine = true,
                        enabled = !busy,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Text("金鑰只保留在目前應用程式記憶體；關閉後不保存。", style = MaterialTheme.typography.bodySmall)
                }
            }

            item {
                SectionCard("房間照片") {
                    OutlinedButton(
                        onClick = { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
                        enabled = !busy,
                        modifier = Modifier.fillMaxWidth()
                    ) { Text(stringResource(R.string.photo_picker_action)) }
                    Button(
                        onClick = {
                            var captureFile: File? = null
                            try {
                                val (file, uri) = CameraCaptureStore.create(context)
                                captureFile = file
                                pendingCapturePath = file.absolutePath
                                camera.launch(uri)
                            } catch (_: Exception) {
                                pendingCapturePath = null
                                CameraCaptureStore.delete(captureFile)
                                errorMessage = "無法啟動相機拍照。"
                            }
                        },
                        enabled = !busy,
                        modifier = Modifier.fillMaxWidth()
                    ) { Text(stringResource(R.string.camera_capture_action)) }
                    roomImage?.let { image ->
                        PhotoWithOverlays(image, analysisSnapshot?.analysis)
                        Text(
                            "${image.sourceName}｜${image.width} × ${image.height}｜JPEG${if (image.resized) "（已等比例縮小）" else ""}",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                    Text("可使用 Android Photo Picker 或系統相機；照片只在記憶體與應用程式快取中處理，預設不保存至相簿。", style = MaterialTheme.typography.bodySmall)
                }
            }

            item {
                SectionCard("分析目標與限制") {
                    ChoiceDropdown("主要目標", goal.label, MainGoal.entries.map { it.label }, !busy) {
                        goal = MainGoal.entries.first { item -> item.label == it }
                    }
                    ChoiceDropdown("風格偏好", style.label, StylePreference.entries.map { it.label }, !busy) {
                        style = StylePreference.entries.first { item -> item.label == it }
                    }
                    ToggleRow("允許購買新物品", allowPurchases, !busy) { allowPurchases = it }
                    ToggleRow("允許移動大型家具", allowFurnitureMovement, !busy) { allowFurnitureMovement = it }
                    OutlinedTextField(
                        value = preserveItems,
                        onValueChange = { if (it.length <= 1000) preserveItems = it },
                        label = { Text("必須保留的物品或家具") },
                        enabled = !busy,
                        modifier = Modifier.fillMaxWidth()
                    )
                    OutlinedTextField(
                        value = extraConstraints,
                        onValueChange = { if (it.length <= 1500) extraConstraints = it },
                        label = { Text("其他實際限制") },
                        enabled = !busy,
                        modifier = Modifier.fillMaxWidth()
                    )
                    Text("固定限制：保留現有牆壁、門、窗與房間結構。", color = RoomGreen, fontWeight = FontWeight.SemiBold)
                }
            }

            item {
                Button(
                    onClick = { runAnalysis() },
                    enabled = !busy && roomImage != null && apiKey.isNotBlank() && selectedModel == ProviderModel.NVIDIA,
                    modifier = Modifier.fillMaxWidth()
                ) { Text("分析照片") }
                if (selectedModel == ProviderModel.OPENAI && analysisSnapshot == null) {
                    Text("請先選擇 NVIDIA 模型完成 Phase 1A/1B 分析。", style = MaterialTheme.typography.bodySmall)
                }
            }

            if (busy) item {
                Card(colors = CardDefaults.cardColors(containerColor = Color(0xFFE4EEE8))) {
                    Text("$busyLabel · 已經過 ${elapsedSeconds} 秒", modifier = Modifier.padding(14.dp), color = RoomGreen, fontWeight = FontWeight.Bold)
                }
            }
            errorMessage?.let { message -> item {
                Card(colors = CardDefaults.cardColors(containerColor = ErrorBackground)) {
                    Text(message, modifier = Modifier.padding(14.dp), color = MaterialTheme.colorScheme.error)
                }
            } }

            analysisSnapshot?.let { snapshot ->
                item { AnalysisHeader(snapshot.analysis) }
                item {
                    VisualActionPlan(
                        analysis = snapshot.analysis,
                        completion = completion,
                        onState = { id, state -> completion[id] = state }
                    )
                }
                item { RecommendationList(snapshot.analysis, completion) }
                item { ObservationList(snapshot.analysis.observations) }
                item { TextLists(snapshot.analysis) }
                item {
                    OutlinedButton(
                        onClick = { runAnalysis() },
                        enabled = !busy && selectedModel == ProviderModel.NVIDIA && apiKey.isNotBlank(),
                        modifier = Modifier.fillMaxWidth()
                    ) { Text("使用目前設定重試") }
                }
            }

            item {
                Phase2APanel(
                    selectedModel = selectedModel,
                    configured = apiKey.isNotBlank(),
                    available = previewContextCurrent,
                    busy = busy,
                    generated = generatedPreview,
                    onGenerate = { runPreview() }
                )
            }
        }
    }
}

@Composable
private fun SectionCard(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = Color.White), shape = RoundedCornerShape(16.dp)) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            content()
        }
    }
}

@Composable
private fun ChoiceDropdown(
    label: String,
    selected: String,
    values: List<String>,
    enabled: Boolean,
    onSelect: (String) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    Column {
        Text(label, style = MaterialTheme.typography.labelLarge)
        Box {
            OutlinedButton(
                onClick = { expanded = true }, enabled = enabled,
                modifier = Modifier.fillMaxWidth()
            ) { Text(selected, modifier = Modifier.weight(1f)); Text("▾") }
            DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                values.forEach { value ->
                    DropdownMenuItem(text = { Text(value) }, onClick = {
                        expanded = false
                        onSelect(value)
                    })
                }
            }
        }
    }
}

@Composable
private fun ToggleRow(label: String, checked: Boolean, enabled: Boolean, onChange: (Boolean) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
        Text(label, modifier = Modifier.weight(1f))
        Switch(checked = checked, onCheckedChange = onChange, enabled = enabled)
    }
}

@Composable
private fun PhotoWithOverlays(image: ProcessedRoomImage, analysis: RoomAnalysis?) {
    Box(
        modifier = Modifier.fillMaxWidth().aspectRatio(image.width.toFloat() / image.height.toFloat())
            .clip(RoundedCornerShape(12.dp)).background(Color(0xFF1D211E))
    ) {
        Image(
            bitmap = image.bitmap.asImageBitmap(), contentDescription = "已校正的房間照片",
            modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Fit
        )
        if (analysis != null) EvidenceCanvas(analysis)
    }
}

@Composable
private fun EvidenceCanvas(analysis: RoomAnalysis) {
    val observations = analysis.observations.associateBy { it.observationId }
    val ordered = analysis.recommendations.sortedWith(compareBy<Recommendation> { it.priority.rank })
    Canvas(Modifier.fillMaxSize()) {
        analysis.observations.forEach { observation ->
            observation.approximateBbox?.let { box -> drawBox(box, Color(0xFFFFB449), 2.dp.toPx()) }
        }
        ordered.forEachIndexed { index, recommendation ->
            if (!recommendation.visualActionAvailable) return@forEachIndexed
            val source = recommendation.supportingObservationIds.asSequence()
                .mapNotNull { observations[it] }.firstOrNull { it.approximateBbox != null }
            val sourceBox = source?.approximateBbox ?: return@forEachIndexed
            drawBox(sourceBox, Color(0xFFE95F37), 3.dp.toPx())
            val sourceCenter = center(sourceBox)
            val destinationBox = recommendation.destinationObservationId
                ?.let { observations[it]?.approximateBbox }
            destinationBox?.let { destination ->
                drawBox(destination, Color(0xFF4C8C69), 3.dp.toPx())
                drawArrow(sourceCenter, center(destination), Color(0xFFE95F37), 3.dp.toPx())
            }
            drawCircle(Color(0xFFE95F37), 14.dp.toPx(), sourceCenter)
            drawContext.canvas.nativeCanvas.drawText(
                "${index + 1}", sourceCenter.x, sourceCenter.y + 5.dp.toPx(),
                Paint().apply { color = android.graphics.Color.WHITE; textSize = 14.dp.toPx(); textAlign = Paint.Align.CENTER; isFakeBoldText = true }
            )
        }
    }
}

private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawBox(box: BoundingBox, color: Color, width: Float) {
    drawRect(
        color = color,
        topLeft = Offset(box.xMin * size.width, box.yMin * size.height),
        size = Size((box.xMax - box.xMin) * size.width, (box.yMax - box.yMin) * size.height),
        style = Stroke(width)
    )
}

private fun androidx.compose.ui.graphics.drawscope.DrawScope.center(box: BoundingBox): Offset = Offset(
    ((box.xMin + box.xMax) / 2f) * size.width,
    ((box.yMin + box.yMax) / 2f) * size.height
)

private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawArrow(from: Offset, to: Offset, color: Color, width: Float) {
    drawLine(color, from, to, strokeWidth = width, cap = StrokeCap.Round)
    val angle = atan2(to.y - from.y, to.x - from.x)
    val length = 12.dp.toPx()
    val left = Offset(to.x - length * cos(angle - 0.5f), to.y - length * sin(angle - 0.5f))
    val right = Offset(to.x - length * cos(angle + 0.5f), to.y - length * sin(angle + 0.5f))
    val path = Path().apply { moveTo(to.x, to.y); lineTo(left.x, left.y); lineTo(right.x, right.y); close() }
    drawPath(path, color)
}

@Composable
private fun AnalysisHeader(analysis: RoomAnalysis) {
    SectionCard("照片實證分析") {
        Text(analysis.roomSummary, fontWeight = FontWeight.Bold)
        Text(analysis.inputSuitability.explanation, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun VisualActionPlan(
    analysis: RoomAnalysis,
    completion: Map<String, CompletionState>,
    onState: (String, CompletionState) -> Unit
) {
    val ordered = analysis.recommendations.sortedWith(compareBy<Recommendation> { it.priority.rank })
    val completed = completion.values.count { it == CompletionState.COMPLETED }
    SectionCard("視覺行動計畫") {
        Text("$completed / ${ordered.size} 已完成", color = RoomGreen, fontWeight = FontWeight.Bold)
        if (ordered.isEmpty()) Text("目前沒有可執行的行動。")
        ordered.forEachIndexed { index, recommendation ->
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = if (completion[recommendation.recommendationId] == CompletionState.COMPLETED) Color(0xFFEFF8F1) else RoomBackground
                )
            ) {
                Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("${index + 1}. ${recommendation.action}", fontWeight = FontWeight.SemiBold)
                    Text(
                        if (recommendation.destinationObservationId != null) "照片已標示可見來源與目的地。"
                        else recommendation.visualActionNote ?: recommendation.confirmationNeeded ?: "目的地無法由照片確認，保留為文字行動。",
                        style = MaterialTheme.typography.bodySmall
                    )
                    CompletionDropdown(
                        completion[recommendation.recommendationId] ?: CompletionState.PENDING
                    ) { onState(recommendation.recommendationId, it) }
                }
            }
        }
    }
}

@Composable
private fun CompletionDropdown(value: CompletionState, onSelect: (CompletionState) -> Unit) {
    ChoiceDropdown("處理狀態", value.label, CompletionState.entries.map { it.label }, true) { selected ->
        onSelect(CompletionState.entries.first { it.label == selected })
    }
}

@Composable
private fun RecommendationList(analysis: RoomAnalysis, completion: Map<String, CompletionState>) {
    SectionCard("優先建議") {
        analysis.recommendations.sortedWith(compareBy<Recommendation> { it.priority.rank }).forEach { item ->
            Card(colors = CardDefaults.cardColors(containerColor = Color(0xFFFCFDFB))) {
                Column(Modifier.fillMaxWidth().padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Text("${item.priority.label}｜${item.targetItemOrArea}", fontWeight = FontWeight.Bold)
                    Text(item.action)
                    Text("實際理由：${item.practicalReason}")
                    item.destinationOrArrangement?.let { Text("位置／安排：$it") }
                    item.aestheticRationale?.let { Text("視覺考量：$it") }
                    item.confirmationNeeded?.let { Text("執行前確認：$it") }
                    item.noPurchaseAlternative?.let { Text("免購買替代：$it") }
                    Text("狀態：${(completion[item.recommendationId] ?: CompletionState.PENDING).label}", color = RoomGreen)
                }
            }
        }
    }
}

@Composable
private fun ObservationList(observations: List<Observation>) {
    SectionCard("照片觀察證據") {
        observations.forEachIndexed { index, item ->
            Column {
                Text("${index + 1}. ${item.visibleItemOrArea}", fontWeight = FontWeight.Bold)
                Text(item.positionDescription)
                Text("可見證據：${item.visibleEvidence}")
                if (item.uncertain) Text("此觀察有不確定性", color = Color(0xFFC77723))
            }
            HorizontalDivider()
        }
    }
}

@Composable
private fun TextLists(analysis: RoomAnalysis) {
    SectionCard("不確定事項與分析限制") {
        Text("不確定事項", fontWeight = FontWeight.Bold)
        if (analysis.uncertainties.isEmpty()) Text("未列出其他不確定事項。")
        analysis.uncertainties.forEach { Text("• $it") }
        Spacer(Modifier.height(4.dp))
        Text("分析限制", fontWeight = FontWeight.Bold)
        if (analysis.limitations.isEmpty()) Text("未列出其他分析限制。")
        analysis.limitations.forEach { Text("• $it") }
    }
}

@Composable
private fun Phase2APanel(
    selectedModel: ProviderModel,
    configured: Boolean,
    available: Boolean,
    busy: Boolean,
    generated: android.graphics.Bitmap?,
    onGenerate: () -> Unit
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = WarningBackground),
        shape = RoundedCornerShape(16.dp),
        modifier = Modifier.fillMaxWidth().border(2.dp, Color(0xFFD89A3B), RoundedCornerShape(16.dp))
    ) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("AI 整理預覽", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text("⚠ 此功能尚未實際測試", color = Color(0xFF8A3C12), fontSize = 18.sp, fontWeight = FontWeight.ExtraBold)
            Text("AI 整理預覽為生成式模擬結果，不代表實際整理後一定會呈現相同效果。", fontWeight = FontWeight.Bold)
            val stateText = when {
                selectedModel != ProviderModel.OPENAI -> "請選擇 OpenAI — gpt-image-2.5-sunburst。"
                !configured -> "請輸入目前 OpenAI 模型使用的 API_KEY。"
                !available -> "需先完成與目前照片及限制綁定的有效 Phase 1B 分析。"
                else -> "已綁定目前照片、建議與限制，可產生一張預覽。"
            }
            Text(stateText, style = MaterialTheme.typography.bodySmall)
            Button(
                onClick = onGenerate,
                enabled = selectedModel == ProviderModel.OPENAI && configured && available && !busy,
                modifier = Modifier.fillMaxWidth()
            ) { Text("產生 AI 整理預覽") }
            generated?.let {
                Text("AI 整理預覽", color = RoomGreen, fontWeight = FontWeight.ExtraBold)
                Image(
                    bitmap = it.asImageBitmap(), contentDescription = "AI 整理預覽生成式模擬結果",
                    modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)),
                    contentScale = ContentScale.FillWidth
                )
            }
        }
    }
}
