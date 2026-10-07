package com.tigerai.roomstyler.validation

import com.tigerai.roomstyler.model.AnalysisConstraints
import com.tigerai.roomstyler.model.UserFacingException
import com.tigerai.roomstyler.network.NvidiaNimClient
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class OptionalAnalysisListsTest {
    private val constraints = AnalysisConstraints()
    private fun fixture(): JSONObject = JSONObject(javaClass.getResourceAsStream("/web_analysis.json")!!
        .bufferedReader(Charsets.UTF_8).use { it.readText() })
    private fun parse(value: JSONObject) = AnalysisContract.parseAndValidate(value.toString(), constraints)
    private fun withoutLists(): JSONObject = fixture().apply {
        remove("limitations")
        remove("uncertainties")
    }

    @Test fun missingLimitationsIsEmpty() {
        val value = fixture().apply { remove("limitations") }
        val result = parse(value)
        assertTrue(result.limitations.isEmpty())
        assertEquals(1, result.uncertainties.size)
    }

    @Test fun missingUncertaintiesIsEmpty() {
        val value = fixture().apply { remove("uncertainties") }
        val result = parse(value)
        assertTrue(result.uncertainties.isEmpty())
        assertEquals(1, result.limitations.size)
    }

    @Test fun nullAndMissingListsWorkThroughActualNvidiaResponseParser() {
        for (key in listOf("limitations", "uncertainties")) {
            val value = withoutLists().put(key, JSONObject.NULL)
            val body = JSONObject().put("choices", JSONArray().put(JSONObject()
                .put("finish_reason", "stop").put("message", JSONObject().put("content", value.toString()))))
            val result = NvidiaNimClient.parseResponse(body.toString().toByteArray(Charsets.UTF_8), constraints)
            assertTrue(result.limitations.isEmpty())
            assertTrue(result.uncertainties.isEmpty())
        }
        val result = parse(fixture().put("limitations", JSONObject.NULL).put("uncertainties", JSONObject.NULL))
        assertTrue(result.limitations.isEmpty())
        assertTrue(result.uncertainties.isEmpty())
    }

    @Test fun existingListsArePreserved() {
        val value = fixture()
        val result = parse(value)
        assertEquals(value.getJSONArray("limitations").getString(0), result.limitations.single())
        assertEquals(value.getJSONArray("uncertainties").getString(0), result.uncertainties.single())
    }

    @Test fun malformedListValuesAndElementsStillFail() {
        for (key in listOf("limitations", "uncertainties")) {
            for (bad in listOf("", JSONObject(), false, 0, JSONArray().put(JSONObject.NULL),
                JSONArray().put(""), JSONArray().put("x".repeat(801)))) {
                assertThrows(UserFacingException::class.java) { parse(fixture().put(key, bad)) }
            }
        }
    }

    @Test fun absentOrNullCoreFieldsRemainRequired() {
        for (key in listOf("input_suitability", "room_summary", "observations", "recommendations")) {
            val missing = withoutLists().apply { remove(key) }
            assertThrows(UserFacingException::class.java) { parse(missing) }
            assertThrows(UserFacingException::class.java) { parse(withoutLists().put(key, JSONObject.NULL)) }
        }
    }

    @Test fun idsReferencesAndCoreRecommendationFieldsRemainRequired() {
        val observation = withoutLists().apply { getJSONArray("observations").getJSONObject(0).remove("observation_id") }
        assertThrows(UserFacingException::class.java) { parse(observation) }
        for (key in listOf("recommendation_id", "priority", "supporting_observation_ids", "target_item_or_area",
            "action", "practical_reason", "requires_purchase", "moves_large_furniture", "requires_confirmation")) {
            val value = withoutLists().apply { getJSONArray("recommendations").getJSONObject(0).remove(key) }
            assertThrows(UserFacingException::class.java) { parse(value) }
        }
    }

    @Test fun semanticChecksStillRejectInvalidResultsAfterNormalization() {
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.getJSONArray("recommendations").getJSONObject(0).put("supporting_observation_ids", JSONArray().put("obs_99")) },
            { it.getJSONArray("observations").put(JSONObject(it.getJSONArray("observations").getJSONObject(0).toString())) },
            { it.getJSONArray("recommendations").put(JSONObject(it.getJSONArray("recommendations").getJSONObject(0).toString())) },
            { it.getJSONArray("observations").getJSONObject(0).getJSONObject("approximate_bbox").put("x_min", 0.9) },
            { it.getJSONArray("recommendations").getJSONObject(0).put("requires_purchase", true) },
            { it.getJSONArray("recommendations").getJSONObject(0).put("moves_large_furniture", true) },
            {
                val rec = it.getJSONArray("recommendations").getJSONObject(0).toString()
                it.put("recommendations", JSONArray().apply {
                    for (index in 1..6) put(JSONObject(rec).put("recommendation_id", "rec_$index"))
                })
            },
            { it.getJSONArray("recommendations").getJSONObject(0).put("destination_observation_id", "obs_99") },
            {
                it.getJSONArray("recommendations").getJSONObject(0).put("destination_observation_id", "obs_1")
                it.getJSONArray("observations").getJSONObject(0).put("approximate_bbox", JSONObject.NULL)
            },
            { it.getJSONArray("recommendations").getJSONObject(0).put("action", "使用束帶整理線材。") }
        )
        for (mutate in mutations) {
            val value = withoutLists().put("uncertainties", JSONObject.NULL)
            mutate(value)
            assertThrows(UserFacingException::class.java) { parse(value) }
        }
    }
}
