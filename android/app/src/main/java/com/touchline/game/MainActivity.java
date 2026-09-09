package com.touchline.game;

import android.app.Activity;
import android.content.res.AssetManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.ConsoleMessage;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/**
 * Minimal Android shell for the Touchline web game.
 *
 * The game itself is untouched: its Python simulation engine is embedded in the
 * APK by Chaquopy and started on a background thread, listening on 127.0.0.1.
 * This activity does nothing but host a WebView pointed at that local server,
 * plus the usual mobile-game behaviours (back navigation, no zoom, screen on).
 *
 * No internet access is required at runtime.
 */
public class MainActivity extends Activity {

    private static final String HOST = "127.0.0.1";
    private static final int PORT = 8000;
    private static final String HOME = "http://" + HOST + ":" + PORT + "/";

    private WebView web;
    private LinearLayout splash;
    private TextView splashMsg;
    private volatile boolean serverUp = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.parseColor("#0b0e14"));

        web = new WebView(this);
        configureWebView(web);
        root.addView(web, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));

        splash = buildSplash();
        root.addView(splash, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));

        setContentView(root);

        final File files = getFilesDir();
        final File www = new File(files, "www");

        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    setMsg("Unpacking game files…");
                    copyAssets("game", www);
                    setMsg("Starting simulation engine…");
                    if (!Python.isStarted()) {
                        Python.start(new AndroidPlatform(MainActivity.this));
                    }
                    Python.getInstance().getModule("bootstrap")
                          .callAttr("start", files.getAbsolutePath(), www.getAbsolutePath(), PORT);
                    setMsg("Building the world (first launch only)…");
                    for (int i = 0; i < 360; i++) {          // up to 3 minutes
                        if (probe()) {
                            serverUp = true;
                            runOnUiThread(new Runnable() {
                                @Override public void run() { web.loadUrl(HOME); }
                            });
                            return;
                        }
                        try { Thread.sleep(500); } catch (InterruptedException e) { return; }
                    }
                    setMsg("The engine took too long to start. Please close and reopen the app.");
                } catch (final Throwable t) {
                    setMsg("Startup failed: " + t);
                }
            }
        }, "touchline-boot").start();
    }

    /* ------------------------------------------------------------ WebView */

    private void configureWebView(WebView w) {
        WebSettings s = w.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(true);
        s.setUseWideViewPort(true);
        s.setLoadWithOverviewMode(true);
        s.setSupportZoom(false);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setTextZoom(100);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setCacheMode(WebSettings.LOAD_DEFAULT);
        s.setJavaScriptCanOpenWindowsAutomatically(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        if (android.os.Build.VERSION.SDK_INT >= 26) {
            s.setSafeBrowsingEnabled(false);
        }
        w.setBackgroundColor(Color.parseColor("#0b0e14"));
        w.setOverScrollMode(View.OVER_SCROLL_NEVER);
        w.setLongClickable(false);
        w.setOnLongClickListener(new View.OnLongClickListener() {
            @Override public boolean onLongClick(View v) { return true; }   // no text selection popups
        });
        w.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String u = request.getUrl().toString();
                // keep local game traffic inside the WebView, never hand anything to a browser
                return !(u.startsWith("http://" + HOST) || u.startsWith("http://localhost")
                        || u.startsWith("about:") || u.startsWith("data:") || u.startsWith("blob:"));
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                if (url != null && url.startsWith(HOME) && splash.getVisibility() == View.VISIBLE) {
                    splash.setVisibility(View.GONE);
                }
            }
        });
        w.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onConsoleMessage(ConsoleMessage cm) {
                return true;    // silence page logging
            }
        });
    }

    /* -------------------------------------------------------------- splash */

    private LinearLayout buildSplash() {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setGravity(Gravity.CENTER);
        box.setBackgroundColor(Color.parseColor("#0b0e14"));
        box.setClickable(true);

        TextView title = new TextView(this);
        title.setText("TOUCHLINE");
        title.setTextColor(Color.parseColor("#39d98a"));
        title.setTextSize(34);
        title.setTypeface(Typeface.create(Typeface.MONOSPACE, Typeface.BOLD));
        title.setLetterSpacing(0.25f);
        title.setGravity(Gravity.CENTER);
        box.addView(title);

        TextView sub = new TextView(this);
        sub.setText("A football management simulation");
        sub.setTextColor(Color.parseColor("#8a93a6"));
        sub.setTextSize(13);
        sub.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = 12;
        box.addView(sub, lp);

        ProgressBar bar = new ProgressBar(this);
        LinearLayout.LayoutParams blp = new LinearLayout.LayoutParams(72, 72);
        blp.topMargin = 48;
        box.addView(bar, blp);

        splashMsg = new TextView(this);
        splashMsg.setText("Starting…");
        splashMsg.setTextColor(Color.parseColor("#c8d0e0"));
        splashMsg.setTextSize(13);
        splashMsg.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams mlp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        mlp.topMargin = 28;
        box.addView(splashMsg, mlp);
        return box;
    }

    private void setMsg(final String text) {
        runOnUiThread(new Runnable() {
            @Override public void run() {
                if (splashMsg != null) splashMsg.setText(text);
            }
        });
    }

    /* -------------------------------------------------------------- assets */

    /** Copy assets/<src> into <dest>, preserving the tree. Small (≈115 KB). */
    private void copyAssets(String src, File dest) throws Exception {
        AssetManager am = getAssets();
        String[] children = am.list(src);
        if (children == null) return;
        if (children.length == 0) {                  // a file
            InputStream in = am.open(src);
            dest.getParentFile().mkdirs();
            OutputStream out = new FileOutputStream(dest);
            byte[] buf = new byte[16384];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            out.close();
            in.close();
            return;
        }
        dest.mkdirs();
        for (String child : children) {
            copyAssets(src + "/" + child, new File(dest, child));
        }
    }

    /* --------------------------------------------------------------- probe */

    private boolean probe() {
        HttpURLConnection c = null;
        try {
            c = (HttpURLConnection) new URL(HOME + "api/boot").openConnection();
            c.setConnectTimeout(1200);
            c.setReadTimeout(2500);
            c.setRequestMethod("GET");
            int code = c.getResponseCode();
            return code == 200;
        } catch (Exception e) {
            return false;
        } finally {
            if (c != null) c.disconnect();
        }
    }

    /* ------------------------------------------------------------ lifecycle */

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && web != null && web.canGoBack()) {
            web.goBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    protected void onPause() {
        if (web != null) web.onPause();
        super.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (web != null) web.onResume();
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.stopLoading();
            web.destroy();
        }
        super.onDestroy();
    }
}
