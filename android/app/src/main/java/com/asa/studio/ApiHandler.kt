package com.asa.studio

import android.util.Base64
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.InputStream
import java.util.concurrent.TimeUnit
import java.util.regex.Pattern

object ApiHandler {

    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .build()

    private val IMG_URL_PATTERN = Pattern.compile(
        "!\\[.*?\\]\\((https?://[^\\s)]+)\\)|(https?://[^\\s]+\\.(?:png|jpg|jpeg|gif|webp))",
        Pattern.CASE_INSENSITIVE
    )

    data class GenerateResult(
        val filename: String = "",
        val imageB64: String = "",
        val text: String = "",
        val noImage: Boolean = false
    )

    suspend fun generate(
        provider: String,
        prompt: String,
        model: String,
        size: String,
        apiKey: String,
        baseUrl: String,
        imageB64: String?
    ): GenerateResult = withContext(Dispatchers.IO) {
        when (provider) {
            "openai-compatible" -> generateOpenAICompat(prompt, model, apiKey, baseUrl, imageB64)
            "openai"            -> generateDalle(prompt, model, size, apiKey)
            "dashscope"         -> generateDashScope(prompt, model, size, apiKey, imageB64)
            "stability"         -> generateStability(prompt, size, apiKey, imageB64)
            else -> throw Exception("Unknown provider: $provider")
        }
    }

    suspend fun test(provider: String, apiKey: String, baseUrl: String): String = withContext(Dispatchers.IO) {
        when (provider) {
            "openai-compatible" -> testOpenAICompat(apiKey, baseUrl)
            "openai"            -> testOpenAI(apiKey)
            "dashscope"         -> testDashScope(apiKey)
            "stability"         -> testStability(apiKey)
            else -> throw Exception("Unknown provider: $provider")
        }
    }

    // ── OpenAI-compatible (chat API → image URLs in markdown) ──
    private fun generateOpenAICompat(
        prompt: String, model: String, apiKey: String, baseUrl: String, imageB64: String?
    ): GenerateResult {
        val url = baseUrl.trimEnd('/') + "/chat/completions"
        val messages = JSONArray()

        if (imageB64 != null) {
            val content = JSONArray()
            content.put(JSONObject().apply {
                put("type", "text"); put("text", prompt)
            })
            content.put(JSONObject().apply {
                put("type", "image_url")
                put("image_url", JSONObject().apply {
                    put("url", "data:image/png;base64,$imageB64")
                })
            })
            messages.put(JSONObject().apply {
                put("role", "user"); put("content", content)
            })
        } else {
            messages.put(JSONObject().apply {
                put("role", "user"); put("content", prompt)
            })
        }

        val body = JSONObject().apply {
            put("model", model)
            put("messages", messages)
            put("max_tokens", 2000)
        }

        val resp = postJson(url, apiKey, body)
        val text = resp.optJSONArray("choices")
            ?.optJSONObject(0)
            ?.optJSONObject("message")
            ?.optString("content", "") ?: ""

        val urls = extractImageUrls(text)
        if (urls.isEmpty()) return GenerateResult(text = text, noImage = true)

        val imgBytes = downloadBytes(urls.first())
        val b64 = Base64.encodeToString(imgBytes, Base64.NO_WRAP)
        val filename = "generated_${System.currentTimeMillis()}.png"
        return GenerateResult(filename = filename, imageB64 = b64, text = text)
    }

    private fun testOpenAICompat(apiKey: String, baseUrl: String): String {
        val url = baseUrl.trimEnd('/') + "/models"
        val resp = getJson(url, apiKey)
        val models = resp.optJSONArray("data") ?: JSONArray()
        val ids = mutableListOf<String>()
        for (i in 0 until models.length()) {
            ids.add(models.getJSONObject(i).optString("id", ""))
        }
        return "连接成功，可用模型: ${ids.joinToString(", ")}"
    }

    // ── OpenAI DALL·E ──
    private fun generateDalle(
        prompt: String, model: String, size: String, apiKey: String
    ): GenerateResult {
        val dalleSize = mapDalleSize(size)
        val body = JSONObject().apply {
            put("model", model)
            put("prompt", prompt)
            put("size", dalleSize)
            put("n", 1)
            put("response_format", "b64_json")
        }
        val resp = postJson("https://api.openai.com/v1/images/generations", apiKey, body)
        val b64 = resp.optJSONArray("data")
            ?.optJSONObject(0)
            ?.optString("b64_json", "") ?: ""
        val filename = "generated_${System.currentTimeMillis()}.png"
        return GenerateResult(filename = filename, imageB64 = b64)
    }

    private fun mapDalleSize(size: String): String {
        val ratio = size.split(" ")[0]
        return when (ratio) {
            "16:9", "3:2", "21:9" -> "1792x1024"
            "9:16", "2:3" -> "1024x1792"
            else -> "1024x1024"
        }
    }

    private fun testOpenAI(apiKey: String): String {
        val resp = getJson("https://api.openai.com/v1/models", apiKey)
        val models = resp.optJSONArray("data") ?: JSONArray()
        val dalleModels = mutableListOf<String>()
        for (i in 0 until models.length()) {
            val id = models.getJSONObject(i).optString("id", "")
            if (id.startsWith("dall-e")) dalleModels.add(id)
        }
        return if (dalleModels.isNotEmpty()) "连接成功: ${dalleModels.joinToString(", ")}"
        else "连接成功"
    }

    // ── DashScope 百炼 ──
    private val DASHSCOPE_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"

    private suspend fun generateDashScope(
        prompt: String, model: String, size: String, apiKey: String, imageB64: String?
    ): GenerateResult {
        val dashSize = mapDashScopeSize(size)
        val input = JSONObject().apply {
            put("prompt", prompt)
        }
        if (imageB64 != null && !model.contains("cosplay")) {
            input.put("base_image", imageB64)
        }
        if (imageB64 != null && model.contains("cosplay")) {
            input.put("base_image", imageB64)
            input.put("style_image", imageB64)
        }

        val body = JSONObject().apply {
            put("model", model)
            put("input", input)
            put("parameters", JSONObject().apply {
                put("size", dashSize)
                put("n", 1)
            })
        }

        val headers = mapOf(
            "Authorization" to "Bearer $apiKey",
            "X-DashScope-Async" to "enable"
        )
        val resp = postJson(DASHSCOPE_URL, body, headers)
        val taskId = resp.optJSONObject("output")?.optString("task_id", "")
            ?: throw Exception("DashScope submit failed: $resp")

        // Poll (max 60 × 2s = 120s)
        for (i in 0 until 60) {
            delay(2000)
            val pollResp = getJson("$DASHSCOPE_URL/$taskId", apiKey)
            val status = pollResp.optJSONObject("output")?.optString("task_status")
            if (status == "SUCCEEDED") {
                val imgUrl = pollResp.optJSONObject("output")
                    ?.optJSONArray("results")
                    ?.optJSONObject(0)
                    ?.optString("url", "")
                    ?: throw Exception("No image URL in DashScope response")
                val imgBytes = downloadBytes(imgUrl)
                val b64 = Base64.encodeToString(imgBytes, Base64.NO_WRAP)
                val filename = "generated_${System.currentTimeMillis()}.png"
                return GenerateResult(filename = filename, imageB64 = b64)
            }
            if (status == "FAILED") {
                val msg = pollResp.optJSONObject("output")?.optString("message", "")
                throw Exception("DashScope failed: $msg")
            }
        }
        throw Exception("DashScope task timeout (120s)")
    }

    private fun mapDashScopeSize(size: String): String {
        val ratio = size.split(" ")[0]
        return when (ratio) {
            "1:1" -> "1024*1024"
            "4:3" -> "1024*768"
            "3:4" -> "768*1024"
            "16:9" -> "1280*720"
            "9:16" -> "720*1280"
            "3:2" -> "1200*800"
            "2:3" -> "800*1200"
            "21:9" -> "1680*720"
            else -> "1024*1024"
        }
    }

    private fun testDashScope(apiKey: String): String {
        val body = JSONObject().apply {
            put("model", "wanx2.0-t2i-turbo")
            put("input", JSONObject().apply { put("prompt", "test") })
            put("parameters", JSONObject().apply { put("size", "1024*1024"); put("n", 1) })
        }
        val resp = postJson(DASHSCOPE_URL, body, mapOf("Authorization" to "Bearer $apiKey"))
        return "百炼万象连接成功"
    }

    // ── Stability AI ──
    private fun generateStability(
        prompt: String, size: String, apiKey: String, imageB64: String?
    ): GenerateResult {
        val ratio = size.split(" ")[0]
        val endpoint = if (imageB64 == null)
            "https://api.stability.ai/v2beta/stable-image/generate/sd3"
        else
            "https://api.stability.ai/v2beta/stable-image/control/sketch"

        // Build multipart
        val builder = okhttp3.MultipartBody.Builder()
            .setType(okhttp3.MultipartBody.FORM)
            .addFormDataPart("prompt", prompt)
            .addFormDataPart("aspect_ratio", ratio)
            .addFormDataPart("output_format", "png")

        if (imageB64 != null) {
            val imgBytes = Base64.decode(imageB64, Base64.DEFAULT)
            builder.addFormDataPart(
                "image", "image.png",
                imgBytes.toRequestBody("image/png".toMediaType())
            )
        }

        val req = Request.Builder()
            .url(endpoint)
            .header("Authorization", "Bearer $apiKey")
            .header("Accept", "application/json")
            .post(builder.build())
            .build()

        val resp = client.newCall(req).execute()
        if (!resp.isSuccessful) {
            val errBody = resp.body?.string() ?: "Unknown error"
            throw Exception("Stability error (${resp.code}): $errBody")
        }

        val imgBytes = resp.body?.bytes() ?: throw Exception("Stability returned empty body")
        val b64 = Base64.encodeToString(imgBytes, Base64.NO_WRAP)
        val filename = "generated_${System.currentTimeMillis()}.png"
        return GenerateResult(filename = filename, imageB64 = b64)
    }

    private fun testStability(apiKey: String): String {
        val resp = getJson("https://api.stability.ai/v2beta/account/balance", apiKey)
        val credits = resp.optDouble("credits", -1.0)
        return if (credits >= 0) "连接成功，剩余额度: $credits"
        else "连接成功"
    }

    // ── Helpers ──
    private fun extractImageUrls(text: String): List<String> {
        val m = IMG_URL_PATTERN.matcher(text)
        val urls = mutableListOf<String>()
        while (m.find()) {
            val url = m.group(1) ?: m.group(2) ?: continue
            urls.add(url)
        }
        return urls
    }

    private fun downloadBytes(url: String): ByteArray {
        val req = Request.Builder().url(url).build()
        val resp = client.newCall(req).execute()
        if (!resp.isSuccessful) throw Exception("Download failed: HTTP ${resp.code}")
        return resp.body?.bytes() ?: throw Exception("Empty download body")
    }

    private fun postJson(url: String, apiKey: String, body: JSONObject): JSONObject {
        return postJson(url, body, mapOf("Authorization" to "Bearer $apiKey"))
    }

    private fun postJson(url: String, body: JSONObject, headers: Map<String, String>): JSONObject {
        val b = body.toString().toRequestBody("application/json".toMediaType())
        val builder = Request.Builder().url(url).post(b)
        headers.forEach { (k, v) -> builder.header(k, v) }
        val resp = client.newCall(builder.build()).execute()
        val text = resp.body?.string() ?: "{}"
        if (!resp.isSuccessful) throw Exception("HTTP ${resp.code}: $text")
        return JSONObject(text)
    }

    private fun getJson(url: String, apiKey: String): JSONObject {
        val req = Request.Builder()
            .url(url)
            .header("Authorization", "Bearer $apiKey")
            .build()
        val resp = client.newCall(req).execute()
        val text = resp.body?.string() ?: "{}"
        if (!resp.isSuccessful) throw Exception("HTTP ${resp.code}: $text")
        return JSONObject(text)
    }
}
