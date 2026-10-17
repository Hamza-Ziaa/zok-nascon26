/**
 * Zok (ذوق) — Behavioral Telemetry & Dwell-Time Tracking
 * Measures implicit user interest signals without creepy surveillance:
 * - Active reading dwell time per article
 * - Viewport intersection & scroll depth
 * - Outbound link clicks
 */

(function () {
    const articleTimers = {};
    const articleDwell = {};
    const articleMaxScroll = {};
    let activeUserId = null;

    // Detect user ID from edition container or URL
    function getUserId() {
        if (activeUserId) return activeUserId;
        const metaUser = document.querySelector("[data-user-id]");
        if (metaUser) {
            activeUserId = metaUser.dataset.userId;
            return activeUserId;
        }
        const match = window.location.pathname.match(/\/edition\/([^\/]+)/);
        if (match) {
            activeUserId = match[1];
            return activeUserId;
        }
        return "guest";
    }

    function recordInteraction(articleId, clickedOut = false, saved = false) {
        const userId = getUserId();
        const dwell = articleDwell[articleId] || 0.0;
        const scrollDepth = articleMaxScroll[articleId] || 0.5;

        if (dwell < 1.0 && !clickedOut) return; // Ignore fleeting accidental scrolls

        const payload = {
            user_id: userId,
            article_id: articleId,
            dwell_time: parseFloat(dwell.toFixed(1)),
            scroll_depth: parseFloat(scrollDepth.toFixed(2)),
            clicked_out: clickedOut,
            saved: saved,
        };

        if (navigator.sendBeacon) {
            const blob = new Blob([JSON.stringify(payload)], { type: "application/json" });
            navigator.sendBeacon("/api/interact", blob);
        } else {
            fetch("/api/interact", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            }).catch(() => {});
        }
    }

    document.addEventListener("DOMContentLoaded", () => {
        const articleCards = document.querySelectorAll("[data-article-id]");
        if (articleCards.length === 0) return;

        // IntersectionObserver for tracking dwell time while card is visible
        if ("IntersectionObserver" in window) {
            const observer = new IntersectionObserver((entries) => {
                const now = Date.now();
                entries.forEach(entry => {
                    const artId = entry.target.dataset.articleId;
                    if (!artId) return;

                    if (entry.isIntersecting) {
                        articleTimers[artId] = now;
                    } else if (articleTimers[artId]) {
                        const elapsed = (now - articleTimers[artId]) / 1000;
                        articleDwell[artId] = (articleDwell[artId] || 0) + elapsed;
                        delete articleTimers[artId];
                    }
                });
            }, { threshold: 0.35 });

            articleCards.forEach(card => observer.observe(card));
        }

        // Outbound click tracking
        document.querySelectorAll(".click-out").forEach(link => {
            link.addEventListener("click", () => {
                const artId = link.dataset.articleId;
                if (artId) {
                    recordInteraction(artId, true, false);
                }
            });
        });

        // Flush telemetry when page is hidden or unloaded
        window.addEventListener("visibilitychange", () => {
            if (document.visibilityState === "hidden") {
                const now = Date.now();
                Object.keys(articleTimers).forEach(artId => {
                    const elapsed = (now - articleTimers[artId]) / 1000;
                    articleDwell[artId] = (articleDwell[artId] || 0) + elapsed;
                    delete articleTimers[artId];
                    recordInteraction(artId);
                });
            }
        });
    });
})();
