/**
 * Zok (ذوق) — Visual Animations & Micro-Interactions
 */

document.addEventListener("DOMContentLoaded", () => {
    // 1. Scroll-triggered reveal animations
    const animatedElements = document.querySelectorAll(".animate-on-scroll");
    if (animatedElements.length > 0 && "IntersectionObserver" in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const el = entry.target;
                    const delay = el.dataset.delay || 0;
                    setTimeout(() => {
                        el.classList.add("is-visible");
                        el.style.opacity = "1";
                        el.style.transform = "translateY(0)";
                    }, delay);
                    observer.unobserve(el);
                }
            });
        }, { threshold: 0.1, rootMargin: "0px 0px -40px 0px" });

        animatedElements.forEach(el => {
            el.style.opacity = "0";
            el.style.transform = "translateY(16px)";
            el.style.transition = "opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1), transform 0.6s cubic-bezier(0.16, 1, 0.3, 1)";
            observer.observe(el);
        });
    }

    // 2. Reading progress bar
    const progressBar = document.getElementById("reading-progress");
    if (progressBar) {
        window.addEventListener("scroll", () => {
            const docHeight = document.documentElement.scrollHeight - window.innerHeight;
            const scrolled = (window.scrollY / (docHeight || 1)) * 100;
            progressBar.style.width = Math.min(100, Math.max(0, scrolled)) + "%";
        }, { passive: true });
    }

    // 3. Paper unfolding entrance
    const unfoldEl = document.querySelector(".paper-unfold");
    if (unfoldEl) {
        unfoldEl.style.opacity = "0";
        unfoldEl.style.transform = "scale(0.98) translateY(12px)";
        unfoldEl.style.transition = "opacity 0.7s cubic-bezier(0.16, 1, 0.3, 1), transform 0.7s cubic-bezier(0.16, 1, 0.3, 1)";
        requestAnimationFrame(() => {
            unfoldEl.style.opacity = "1";
            unfoldEl.style.transform = "scale(1) translateY(0)";
        });
    }
});
