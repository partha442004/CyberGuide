//
//  ContentView.swift
//  CyberGuide
//
//  Full-screen WKWebView pointed at the live dashboard. Includes pull-to-
//  refresh, back/forward toolbar, and an activity indicator while loading.
//

import SwiftUI
import UIKit
import WebKit

/// The dashboard to load. Swap in your own Streamlit / Vercel URL here.
let kDashboardURL = URL(string: "https://cyberguide2026aug.streamlit.app/")!

struct ContentView: View {
    @State private var isLoading = true
    @State private var canGoBack = false
    @State private var canGoForward = false

    var body: some View {
        VStack(spacing: 0) {
            WebView(
                isLoading: $isLoading,
                canGoBack: $canGoBack,
                canGoForward: $canGoForward
            )

            Divider()

            // Bottom toolbar: back / refresh / forward
            HStack {
                Button(action: { NotificationCenter.default.post(name: .cgGoBack, object: nil) }) {
                    Image(systemName: "chevron.left")
                        .font(.title2)
                }
                .disabled(!canGoBack)

                Spacer()

                Button(action: { NotificationCenter.default.post(name: .cgReload, object: nil) }) {
                    Image(systemName: "arrow.clockwise")
                        .font(.title2)
                }

                Spacer()

                Button(action: { NotificationCenter.default.post(name: .cgGoForward, object: nil) }) {
                    Image(systemName: "chevron.right")
                        .font(.title2)
                }
                .disabled(!canGoForward)
            }
            .padding(.horizontal, 48)
            .padding(.vertical, 10)
            .background(Color(.systemBackground))
        }
        .overlay {
            if isLoading {
                ProgressView("Loading dashboard…")
                    .padding(24)
                    .background(Color(.systemBackground), in: RoundedRectangle(cornerRadius: 12))
                    .shadow(radius: 8)
            }
        }
    }
}

extension Notification.Name {
    static let cgGoBack = Notification.Name("cgGoBack")
    static let cgGoForward = Notification.Name("cgGoForward")
    static let cgReload = Notification.Name("cgReload")
}

struct WebView: UIViewRepresentable {
    @Binding var isLoading: Bool
    @Binding var canGoBack: Bool
    @Binding var canGoForward: Bool

    final class Coordinator: NSObject, WKNavigationDelegate {
        var parent: WebView
        weak var webView: WKWebView?

        init(_ parent: WebView) {
            self.parent = parent
        }

        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation?) {
            parent.isLoading = true
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation?) {
            parent.isLoading = false
            parent.canGoBack = webView.canGoBack
            parent.canGoForward = webView.canGoForward
        }

        func webView(_ webView: WKWebView, didFail navigation: WKNavigation?, withError error: Error) {
            parent.isLoading = false
        }

        @objc func goBack(_ note: Notification? = nil) {
            webView?.goBack()
        }

        @objc func goForward(_ note: Notification? = nil) {
            webView?.goForward()
        }

        @objc func reload(_ note: Notification? = nil) {
            webView?.reload()
        }

        @objc func refresh(_ sender: UIRefreshControl) {
            webView?.reload()
            sender.endRefreshing()
        }
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default()
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = context.coordinator
        context.coordinator.webView = webView

        // Pull-to-refresh
        let refresh = UIRefreshControl()
        refresh.addTarget(context.coordinator, action: #selector(Coordinator.refresh(_:)), for: .valueChanged)
        webView.scrollView.refreshControl = refresh

        // Toolbar notifications
        NotificationCenter.default.addObserver(context.coordinator, selector: #selector(Coordinator.goBack(_:)), name: .cgGoBack, object: nil)
        NotificationCenter.default.addObserver(context.coordinator, selector: #selector(Coordinator.goForward(_:)), name: .cgGoForward, object: nil)
        NotificationCenter.default.addObserver(context.coordinator, selector: #selector(Coordinator.reload(_:)), name: .cgReload, object: nil)

        webView.load(URLRequest(url: kDashboardURL))
        return webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}
}
