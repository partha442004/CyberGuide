package com.cyberguide.app;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.graphics.Bitmap;
import android.os.Bundle;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.ProgressBar;

/**
 * CyberGuide Android — a WebView shell around the live dashboard.
 *
 * The dashboard is a Streamlit web app hosted on Streamlit Community Cloud
 * talking to the Vercel API. This wrapper gives it a native app feel:
 * no URL bar, back/forward navigation, cookies persisted, and JS enabled.
 */
public class MainActivity extends Activity {

    /** Live dashboard URL (Streamlit Community Cloud). */
    private static final String DASHBOARD_URL =
            "https://cyberguide2026aug.streamlit.app/";

    /** Fallback if the user opens a deep link outside the app. */
    private static final String API_HEALTH_URL =
            "https://cyberguide-api.vercel.app/health";

    private WebView webView;
    private ProgressBar progressBar;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        webView = findViewById(R.id.webview);
        progressBar = findViewById(R.id.progress_bar);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setSupportZoom(true);
        settings.setBuiltInZoomControls(true);
        settings.setDisplayZoomControls(false);

        CookieManager.getInstance().setAcceptCookie(true);

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                progressBar.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                progressBar.setVisibility(View.GONE);
            }

            @Override
            public boolean shouldOverrideUrlLoading(
                    WebView view, WebResourceRequest request) {
                // Keep everything inside the WebView (no external browser
                // for the dashboard itself).
                return false;
            }
        });

        webView.setWebChromeClient(new WebChromeClient());

        // If the API is unreachable the dashboard shows its offline state;
        // the WebView still renders. Load the dashboard directly.
        webView.loadUrl(DASHBOARD_URL);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.destroy();
        }
        super.onDestroy();
    }
}
