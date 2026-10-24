package com.sudoku.hundred;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {
    private WebView web;
    private static int renderCrashes = 0;   // 网页进程短时间内连续崩溃的次数：超过 3 次就不再重建，免得无限闪屏
    private static long lastCrash = 0;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        // 有的安装器“打开”后再从桌面图标启动会多开一个：已经有在跑的就直接回到它，免得两份进度互相覆盖
        Intent it = getIntent();
        if (!isTaskRoot() && it != null && it.hasCategory(Intent.CATEGORY_LAUNCHER) && Intent.ACTION_MAIN.equals(it.getAction())) {
            finish();
            return;
        }
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        s.setTextZoom(100);
        s.setSupportZoom(false);
        web.setWebViewClient(new WebViewClient() {
            // 后台时系统把网页进程回收了：重新创建页面（进度每一步都存过），而不是让整个 App 崩掉
            @Override
            public boolean onRenderProcessGone(WebView view, RenderProcessGoneDetail detail) {
                if (view == web) {
                    web = null;
                    ((android.view.ViewGroup) view.getParent()).removeView(view);
                    view.destroy();
                    long now = android.os.SystemClock.elapsedRealtime();
                    if (now - lastCrash > 60000) renderCrashes = 0;   // 隔了一分钟以上才又崩：不算连续
                    lastCrash = now;
                    if (++renderCrashes <= 3) recreate(); else finish();
                }
                return true;
            }
        });
        web.setOverScrollMode(WebView.OVER_SCROLL_NEVER);
        web.setBackgroundColor(getResources().getColor(R.color.bg, getTheme()));
        setContentView(web);
        // 把系统字体缩放比例告诉网页：老人调大了系统字体时，第一次打开会自动进入大字模式
        float fs = getResources().getConfiguration().fontScale;
        web.loadUrl("file:///android_asset/www/index.html#fs=" + String.format(java.util.Locale.US, "%.2f", fs));
    }

    @Override
    public void onBackPressed() {
        if (web == null) { super.onBackPressed(); return; }
        web.evaluateJavascript("window.handleBack && window.handleBack()", value -> {
            if (!"true".equals(value)) MainActivity.super.onBackPressed();
        });
    }

    @Override
    protected void onPause() {
        // 切到后台：停表并存档，然后暂停 WebView
        if (web != null) {
            web.evaluateJavascript("window.appPause && window.appPause()", null);
            web.onPause();
        }
        super.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (web != null) {
            web.onResume();
            web.evaluateJavascript("window.appResume && window.appResume()", null);
        }
    }

    @Override
    protected void onDestroy() {
        if (web != null) web.destroy();
        super.onDestroy();
    }
}
