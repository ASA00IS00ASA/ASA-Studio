# ASA-Studio ProGuard rules
-keepattributes *Annotation*
-keepattributes JavascriptInterface
-keepclassmembers class com.asa.studio.MainActivity$AndroidBridge {
    @android.webkit.JavascriptInterface <methods>;
}
