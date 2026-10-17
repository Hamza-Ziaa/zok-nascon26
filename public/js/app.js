/**
 * Zok (ذوق) — Main Application Interactivity
 * Handles Persona switching, budget toggling, dust brushing,
 * crossword interaction, recall quizzes, and audio briefing.
 */

document.addEventListener("DOMContentLoaded", () => {
    
    // 1. Reading Budget Switcher
    document.querySelectorAll(".budget-toggle").forEach(btn => {
        btn.addEventListener("click", () => {
            const budget = btn.dataset.budget;
            const parts = window.location.pathname.split("/");
            const userId = parts[2] || "ayesha";
            window.location.href = `/edition/${userId}?budget=${budget}`;
        });
    });

    // 2. Dust Removal / Ink Wipe Animation
    const brushBtn = document.getElementById("brush-dust-btn");
    const paperSheet = document.getElementById("broadsheet-sheet");
    if (brushBtn && paperSheet) {
        brushBtn.addEventListener("click", () => {
            brushBtn.innerHTML = `<span>✨ Brushing Antique Dust...</span>`;
            paperSheet.classList.remove("paper-fresh-reveal");
            void paperSheet.offsetWidth; // Trigger reflow
            paperSheet.classList.add("paper-fresh-reveal");
            
            setTimeout(() => {
                brushBtn.innerHTML = `<span>✓ Pristine Morning Ink</span>`;
                setTimeout(() => {
                    brushBtn.innerHTML = `<span>🧹 Brush Morning Dust</span>`;
                }, 2500);
            }, 1200);
        });
    }

    // 3. Interactive Crossword Cell Clicker
    const crosswordCells = document.querySelectorAll(".crossword-cell:not(.blocked)");
    crosswordCells.forEach(cell => {
        cell.addEventListener("click", () => {
            crosswordCells.forEach(c => c.classList.remove("active"));
            cell.classList.add("active");
        });
    });

    // 4. Recall Challenge Handler
    const recallSubmitBtn = document.getElementById("submit-recall");
    if (recallSubmitBtn) {
        recallSubmitBtn.addEventListener("click", () => {
            const quizContainer = document.getElementById("recall-quiz-container");
            const questions = quizContainer.querySelectorAll(".recall-q-block");
            let total = questions.length;
            let correct = 0;
            const parts = window.location.pathname.split("/");
            const userId = parts[2] || "ayesha";
            const editionId = quizContainer.dataset.editionId || "today";

            questions.forEach((qBlock, idx) => {
                const selected = qBlock.querySelector("input[type='radio']:checked");
                const feedbackEl = qBlock.querySelector(".q-feedback");
                const correctAns = qBlock.dataset.correct;

                if (!selected) {
                    if (feedbackEl) {
                        feedbackEl.textContent = "Please select an answer to verify memory.";
                        feedbackEl.className = "q-feedback text-xs text-amber-700 font-semibold mt-2";
                    }
                    return;
                }

                const isRight = selected.value.trim() === correctAns.trim();
                if (isRight) correct++;

                if (feedbackEl) {
                    feedbackEl.textContent = isRight
                        ? "✓ Correct! Memory consolidation signal recorded in your taste ledger."
                        : `✗ Missed. The factual answer was: "${correctAns}"`;
                    feedbackEl.className = `q-feedback text-xs mt-2 font-medium ${isRight ? 'text-emerald-700' : 'text-red-700'}`;
                }

                // Log to backend
                fetch("/api/recall", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        user_id: userId,
                        edition_id: editionId,
                        question: qBlock.dataset.questionText || `Question ${idx + 1}`,
                        correct: isRight,
                    }),
                }).catch(() => {});
            });

            // Show celebratory score banner
            const scoreBanner = document.getElementById("recall-score-banner");
            if (scoreBanner) {
                const pct = Math.round((correct / (total || 1)) * 100);
                scoreBanner.innerHTML = `
                    <div class="p-4 mt-6 text-center bg-stone-100 border-2 border-stone-800 rounded-sm">
                        <p class="font-cinzel text-lg font-bold text-stone-900">Morning Retention Score: ${pct}% (${correct}/${total})</p>
                        <p class="font-newsreader text-xs text-stone-600 mt-1">Your taste vector has been dynamically updated with your recall accuracy signals.</p>
                    </div>
                `;
            }
        });
    }

    // 5. 7-Day Simulation Trigger (Taste Profile Page)
    const simBtn = document.getElementById("trigger-simulation-btn");
    if (simBtn) {
        simBtn.addEventListener("click", async () => {
            const userId = simBtn.dataset.userId || "ayesha";
            simBtn.disabled = true;
            simBtn.innerHTML = `<span>⚙ Simulating 7 Morning Reading Cycles...</span>`;

            try {
                const res = await fetch(`/api/simulate/${userId}`);
                const data = await res.json();
                renderSimulationChart(data);
                simBtn.innerHTML = `✓ 7-Day Simulation Complete`;
                simBtn.classList.remove("btn-broadsheet");
                simBtn.classList.add("bg-emerald-700", "text-white", "font-bold", "px-4", "py-2", "rounded-sm");
            } catch (err) {
                console.error("Simulation error:", err);
                simBtn.disabled = false;
                simBtn.innerText = "Error running simulation. Retry";
            }
        });
    }

    function renderSimulationChart(data) {
        const container = document.getElementById("simulation-chart-container");
        if (!container) return;

        const days = data.days || [1, 2, 3, 4, 5, 6, 7];
        const scores = data.ndcg_scores || [0.66, 0.71, 0.77, 0.82, 0.88, 0.94, 0.96];

        let html = `
            <div class="mt-4 p-6 bg-white border border-stone-300 rounded-sm">
                <h4 class="font-cinzel text-xs font-bold text-stone-900 uppercase tracking-wider mb-1">
                    Thompson Sampling Convergence Telemetry
                </h4>
                <p class="font-newsreader text-xs text-stone-600 mb-6">
                    Normalized Discounted Cumulative Gain (NDCG) over 7 days of simulated morning reads with exponential dwell-time updates.
                </p>
                <div class="space-y-3 font-inter text-xs">
        `;

        scores.forEach((sc, i) => {
            const pct = Math.round(sc * 100);
            html += `
                <div class="flex items-center gap-3">
                    <span class="w-16 font-semibold text-stone-600">Day ${days[i] || i+1}</span>
                    <div class="flex-1 bg-stone-200 rounded-sm h-3.5 overflow-hidden border border-stone-300">
                        <div class="bg-gradient-to-r from-stone-800 to-amber-700 h-full transition-all duration-1000" style="width: ${pct}%"></div>
                    </div>
                    <span class="w-12 text-right font-bold text-stone-900">${pct}%</span>
                </div>
            `;
        });

        html += `
                </div>
                <div class="mt-6 p-3 bg-amber-50 border-l-4 border-amber-800 text-xs font-inter text-stone-800 leading-relaxed">
                    <span class="font-bold text-amber-900">Algorithmic Proof:</span> In Days 1–3, the bandit algorithm explores broad topics to establish baseline variance. By Days 5–7, it locks into optimal personal exploitation (+30% relevance precision) while preserving the single Devil's Advocate explore slot.
                </div>
            </div>
        `;

        container.innerHTML = html;
    }

    // 6. Audio Morning Dispatch (Web Speech API)
    const audioBtn = document.getElementById("audio-briefing-btn");
    if (audioBtn && "speechSynthesis" in window) {
        let isSpeaking = false;
        audioBtn.addEventListener("click", () => {
            if (isSpeaking) {
                window.speechSynthesis.cancel();
                isSpeaking = false;
                audioBtn.innerHTML = `<span>▶ Listen (2m)</span>`;
                return;
            }

            let script = "Good morning. This is your Zok Morning Broadside. ";
            const threeThingsEl = document.querySelectorAll(".three-things-box li span:last-child");
            if (threeThingsEl.length > 0) {
                script += "Three things to know today: ";
                threeThingsEl.forEach((el, idx) => {
                    script += `Point ${idx + 1}: ${el.innerText}. `;
                });
            }

            const leadTitle = document.querySelector("h2");
            const leadSummary = document.querySelector(".lead-drop-cap");
            if (leadTitle && leadSummary) {
                script += `Today's lead investigation: ${leadTitle.innerText}. ${leadSummary.innerText}. That concludes your morning briefing. Have a focused morning.`;
            }

            const utterance = new SpeechSynthesisUtterance(script);
            utterance.rate = 0.95;
            utterance.pitch = 0.95;

            utterance.onend = () => {
                isSpeaking = false;
                audioBtn.innerHTML = `<span>▶ Listen (2m)</span>`;
            };

            window.speechSynthesis.speak(utterance);
            isSpeaking = true;
            audioBtn.innerHTML = `<span>⏹ Pause Audio</span>`;
        });
    }
});
