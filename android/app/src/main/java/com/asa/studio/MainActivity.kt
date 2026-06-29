package com.asa.studio

import android.content.ContentValues
import android.content.Intent
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.MediaStore
import android.util.Base64
import android.view.View
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.FileProvider
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import java.io.File
import java.io.FileOutputStream

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var pendingImageCallback = ""

    private val imagePicker = registerForActivityResult(
        ActivityResultContracts.PickVisualMedia()
    ) { uri: Uri? ->
        if (uri == null || pendingImageCallback.isEmpty()) return@registerForActivityResult
        scope.launch {
            try {
                val inputStream = contentResolver.openInputStream(uri)
                val bytes = inputStream?.readBytes() ?: throw Exception("无法读取图片")
                inputStream.close()
                val b64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
                val mime = contentResolver.getType(uri) ?: "image/png"
                val dataUrl = "data:$mime;base64,$b64"
                evaluateJs("$pendingImageCallback(null, '$dataUrl', '$b64')")
            } catch (e: Exception) {
                evaluateJs("$pendingImageCallback('${e.message}', null, null)")
            }
            pendingImageCallback = ""
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Edge-to-edge with dark status bar
        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.statusBarColor = 0xFF06060E.toInt()
        window.navigationBarColor = 0xFF06060E.toInt()
        WindowInsetsControllerCompat(window, window.decorView).apply {
            isAppearanceLightStatusBars = false
            isAppearanceLightNavigationBars = false
        }

        setContentView(R.layout.activity_main)
        webView = findViewById(R.id.webView)
        setupWebView()
        webView.loadUrl("file:///android_asset/frontend/index.html")
    }

    private fun setupWebView() {
        webView.apply {
            // Transparent bg — no white flash
            setBackgroundColor(0x00000000)

            // Native-feel scrolling
            isVerticalScrollBarEnabled = false
            isHorizontalScrollBarEnabled = false
            overScrollMode = View.OVER_SCROLL_NEVER

            settings.apply {
                javaScriptEnabled = true
                domStorageEnabled = true
                allowFileAccess = true
                allowContentAccess = true
                setSupportZoom(false)
                builtInZoomControls = false
                displayZoomControls = false
                useWideViewPort = true
                loadWithOverviewMode = true
                mixedContentMode = android.webkit.WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                // Disable text selection on long press (native feel)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    // Safe browsing off — not needed for local assets
                }
            }

            addJavascriptInterface(AndroidBridge(), "AndroidBridge")

            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView?, url: String?) {
                    super.onPageFinished(view, url)
                    // Inject CSS to remove tap highlight and improve touch
                    evaluateJavascript("""
                        (function(){
                            var s=document.createElement('style');
                            s.textContent='*{-webkit-tap-highlight-color:transparent;-webkit-touch-callout:none;-webkit-user-select:none;user-select:none;} input,textarea{-webkit-user-select:text;user-select:text;}';
                            document.head.appendChild(s);
                        })();
                    """.trimIndent(), null)
                }

                override fun shouldOverrideUrlLoading(
                    view: WebView?, request: WebResourceRequest?
                ): Boolean {
                    request?.url?.let { url ->
                        if (url.scheme == "http" || url.scheme == "https") {
                            startActivity(Intent(Intent.ACTION_VIEW, url))
                            return true
                        }
                    }
                    return false
                }
            }

            webChromeClient = object : WebChromeClient() {}

            setLayerType(View.LAYER_TYPE_HARDWARE, null)
        }
    }

    inner class AndroidBridge {
        @JavascriptInterface
        fun pickImage(callbackName: String) {
            pendingImageCallback = callbackName
            imagePicker.launch(
                androidx.activity.result.PickVisualMediaRequest(
                    androidx.activity.result.contract.ActivityResultContracts.PickVisualMedia.ImageOnly
                )
            )
        }

        @JavascriptInterface
        fun generateImage(jsonParams: String) {
            scope.launch {
                try {
                    val p = org.json.JSONObject(jsonParams)
                    val result = ApiHandler.generate(
                        provider = p.optString("provider", "openai-compatible"),
                        prompt   = p.optString("prompt", ""),
                        model    = p.optString("model", ""),
                        size     = p.optString("size", "1024x1024"),
                        apiKey   = p.optString("api_key", ""),
                        baseUrl  = p.optString("base_url", ""),
                        imageB64 = p.optString("image_b64", "").ifEmpty { null }
                    )
                    val resp = org.json.JSONObject().apply {
                        put("filename", result.filename)
                        put("image_b64", result.imageB64)
                        put("text", result.text)
                        put("no_image", result.noImage)
                    }
                    evaluateJs("onGenerateResult(null, ${resp})")
                } catch (e: Exception) {
                    evaluateJs("onGenerateResult('${e.message?.replace("'", "\\'")}', null)")
                }
            }
        }

        @JavascriptInterface
        fun testConnection(jsonParams: String) {
            scope.launch {
                try {
                    val p = org.json.JSONObject(jsonParams)
                    val msg = ApiHandler.test(
                        provider = p.optString("provider", ""),
                        apiKey   = p.optString("api_key", ""),
                        baseUrl  = p.optString("base_url", "")
                    )
                    evaluateJs("onTestResult(null, '$msg')")
                } catch (e: Exception) {
                    evaluateJs("onTestResult('${e.message?.replace("'", "\\'")}', null)")
                }
            }
        }

        @JavascriptInterface
        fun saveImage(b64Data: String, filename: String) {
            try {
                val bytes = Base64.decode(b64Data, Base64.DEFAULT)
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    val values = ContentValues().apply {
                        put(MediaStore.Images.Media.DISPLAY_NAME, filename)
                        put(MediaStore.Images.Media.MIME_TYPE, "image/png")
                        put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/ASA-Studio")
                    }
                    contentResolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)?.let {
                        contentResolver.openOutputStream(it)?.use { out -> out.write(bytes) }
                    }
                } else {
                    val dir = File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PICTURES), "ASA-Studio")
                    dir.mkdirs()
                    FileOutputStream(File(dir, filename)).use { it.write(bytes) }
                    MediaStore.Images.Media.insertImage(contentResolver, File(dir, filename).absolutePath, filename, null)
                }
                runOnUiThread { Toast.makeText(this@MainActivity, "已保存到相册", Toast.LENGTH_SHORT).show() }
            } catch (e: Exception) {
                runOnUiThread { Toast.makeText(this@MainActivity, "保存失败: ${e.message}", Toast.LENGTH_SHORT).show() }
            }
        }

        @JavascriptInterface
        fun shareImage(b64Data: String, filename: String) {
            try {
                val bytes = Base64.decode(b64Data, Base64.DEFAULT)
                val dir = File(cacheDir, "share"); dir.mkdirs()
                val file = File(dir, filename)
                FileOutputStream(file).use { it.write(bytes) }
                val uri = FileProvider.getUriForFile(this@MainActivity, "${packageName}.fileprovider", file)
                startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).apply {
                    type = "image/png"; putExtra(Intent.EXTRA_STREAM, uri); addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }, "分享图片"))
            } catch (e: Exception) {
                runOnUiThread { Toast.makeText(this@MainActivity, "分享失败: ${e.message}", Toast.LENGTH_SHORT).show() }
            }
        }

        @JavascriptInterface
        fun showToast(message: String) {
            runOnUiThread { Toast.makeText(this@MainActivity, message, Toast.LENGTH_SHORT).show() }
        }

        @JavascriptInterface
        fun isNativeApp(): Boolean = true
    }

    private fun evaluateJs(script: String) {
        webView.post { webView.evaluateJavascript(script, null) }
    }

    override fun onDestroy() {
        super.onDestroy()
    }

    @Deprecated("Use onBackPressedDispatcher")
    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }
}
