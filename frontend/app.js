// VERITAS Interactive Client Application

document.addEventListener("DOMContentLoaded", () => {
    // DOM Elements
    const demoButtons = document.querySelectorAll(".demo-btn");
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");
    const docTextPreview = document.getElementById("doc-text-preview");
    const userQueryInput = document.getElementById("user-query-input");
    const btnRunAudit = document.getElementById("btn-run-audit");
    
    // Status & Score
    const statusBanner = document.getElementById("status-banner");
    const statusTitle = document.getElementById("status-title");
    const statusSummary = document.getElementById("status-summary");
    const decisionPill = document.getElementById("decision-pill");
    const humanReviewBadge = document.getElementById("human-review-badge");
    
    const compositeScoreNum = document.getElementById("composite-score-num");
    const compositeTier = document.getElementById("composite-tier");
    const barAuth = document.getElementById("bar-auth");
    const barRel = document.getElementById("bar-rel");
    const barRec = document.getElementById("bar-rec");
    const barMeth = document.getElementById("bar-meth");
    const barTrac = document.getElementById("bar-trac");
    const dimAuth = document.getElementById("dim-auth");
    const dimRel = document.getElementById("dim-rel");
    const dimRec = document.getElementById("dim-rec");
    const dimMeth = document.getElementById("dim-meth");
    const dimTrac = document.getElementById("dim-trac");

    // Sections
    const findingsGrid = document.getElementById("findings-grid");
    const explanationBody = document.getElementById("explanation-body");
    const citationPillsRow = document.getElementById("citation-pills-row");
    const supportingList = document.getElementById("supporting-list");
    const conflictSection = document.getElementById("conflict-section");
    const conflictContainer = document.getElementById("conflict-container");
    const missingSection = document.getElementById("missing-section");
    const missingList = document.getElementById("missing-list");
    const questionableSection = document.getElementById("questionable-section");
    const questionableList = document.getElementById("questionable-list");
    const auditLogBox = document.getElementById("audit-log-box");
    const evidenceSvg = document.getElementById("evidence-svg");

    // Modal
    const citationModal = document.getElementById("citation-modal");
    const modalCloseBtn = document.getElementById("modal-close-btn");
    const modalEvId = document.getElementById("modal-ev-id");
    const modalSourceTitle = document.getElementById("modal-source-title");
    const modalSourceName = document.getElementById("modal-source-name");
    const modalScore = document.getElementById("modal-score");
    const modalDate = document.getElementById("modal-date");
    const modalTier = document.getElementById("modal-tier");
    const modalExcerpt = document.getElementById("modal-excerpt");
    const modalUrl = document.getElementById("modal-url");

    let currentDemoId = "demo-1";
    let activeCitations = {};
    let fixtures = [];

    // 1. Fetch Demo Fixtures on Load
    async function loadFixtures() {
        try {
            const res = await fetch("/api/fixtures");
            if (res.ok) {
                fixtures = await res.json();
                selectDemo("demo-1");
            }
        } catch (e) {
            console.error("Failed to load demo fixtures", e);
        }
    }

    // 2. Fetch System Health & LLM Config
    async function loadHealth() {
        try {
            const res = await fetch("/api/health");
            if (res.ok) {
                const data = await res.json();
                document.getElementById("nav-primary-llm").textContent = data.primary_llm.includes("grok") ? "Grok (xAI)" : "Deterministic Core";
                document.getElementById("nav-local-chunks").textContent = `${data.indexed_chunks} Chunks`;
            }
        } catch (e) {
            console.error("Health check error", e);
        }
    }

    // 3. Demo Selection Handler
    function selectDemo(demoId) {
        currentDemoId = demoId;
        demoButtons.forEach(btn => {
            if (btn.dataset.demo === demoId) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
        });

        const selected = fixtures.find(f => f.id === demoId);
        if (selected) {
            docTextPreview.value = selected.document_text;
            userQueryInput.value = selected.user_query;
            addLog(`Loaded Demo Scenario: ${selected.name}`);
        }
    }

    demoButtons.forEach(btn => {
        btn.addEventListener("click", () => selectDemo(btn.dataset.demo));
    });

    // 4. Drag & Drop PDF Handling
    dropZone.addEventListener("click", () => fileInput.click());
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });
    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
    dropZone.addEventListener("drop", async (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length) {
            handleFileUpload(e.target.files[0]);
        }
    });

    async function handleFileUpload(file) {
        if (!file.name.toLowerCase().endsWith(".pdf")) {
            alert("Please upload a valid PDF document (.pdf).");
            return;
        }

        addLog(`Ingesting PDF: ${file.name} (${(file.size / 1024).toFixed(1)} KB)...`);
        const formData = new FormData();
        formData.append("file", file);

        try {
            const res = await fetch("/api/upload", {
                method: "POST",
                body: formData
            });
            if (res.ok) {
                const data = await res.json();
                docTextPreview.value = data.text;
                userQueryInput.value = "Evaluate clinical findings and audit against authoritative reference standards.";
                currentDemoId = null;
                addLog(`PDF parsed successfully: ${data.total_pages} page(s), quality: ${data.extraction_quality}`);
            } else {
                const err = await res.json();
                alert(`Upload failed: ${err.detail || 'Unknown error'}`);
            }
        } catch (e) {
            console.error("Upload error", e);
            alert("Upload failed. Ensure backend server is running.");
        }
    }

    // 5. Run Clinical Evidence Audit
    btnRunAudit.addEventListener("click", runAudit);

    function clearAuditResults() {
        statusTitle.textContent = "Awaiting Document";
        statusSummary.textContent = "Upload a clinical report or select a demo scenario to begin.";
        decisionPill.className = "decision-pill";
        decisionPill.textContent = "READY";
        humanReviewBadge.style.display = "none";
        compositeScoreNum.textContent = "0";
        compositeTier.textContent = "-";
        barAuth.style.width = "0%";
        barRel.style.width = "0%";
        barRec.style.width = "0%";
        barMeth.style.width = "0%";
        barTrac.style.width = "0%";
        dimAuth.textContent = "0%";
        dimRel.textContent = "0%";
        dimRec.textContent = "0%";
        dimMeth.textContent = "0%";
        dimTrac.textContent = "0%";
        const elFindings = document.getElementById("findings-grid");
        if (elFindings) elFindings.innerHTML = "";
        
        const elMissing = document.getElementById("missing-list");
        if (elMissing) elMissing.innerHTML = "";
        
        const elExplanation = document.getElementById("explanation-body");
        if (elExplanation) elExplanation.innerHTML = "";
        
        const elSupporting = document.getElementById("supporting-list");
        if (elSupporting) elSupporting.innerHTML = "";
        
        const elQuestionable = document.getElementById("questionable-list");
        if (elQuestionable) elQuestionable.innerHTML = "";
        
        const elConflict = document.getElementById("conflict-container");
        if (elConflict) elConflict.innerHTML = "";
        
        const elCitationPills = document.getElementById("citation-pills-row");
        if (elCitationPills) elCitationPills.innerHTML = "";
    }

    async function runAudit() {
        const text = docTextPreview.value.trim();
        const query = userQueryInput.value.trim();

        if (!text && !query) {
            alert("Please provide document text or a clinical assessment query.");
            return;
        }

        btnRunAudit.disabled = true;
        btnRunAudit.querySelector("span").textContent = "Auditing Evidence...";
        resetPipelineSteps();
        clearAuditResults();

        // Animate pipeline stages
        await animatePipeline();

        try {
            const payload = {
                document_text: text,
                user_query: query || "What does this clinical report indicate?",
                demo_id: currentDemoId
            };

            const res = await fetch("/api/analyze", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                const data = await res.json();
                renderAuditResults(data);
                completePipeline();
            } else {
                const err = await res.json();
                alert(`Audit error: ${err.detail || 'Analysis failed'}`);
            }
        } catch (e) {
            console.error("Analysis error", e);
            alert("Analysis failed. Check backend connection.");
        } finally {
            btnRunAudit.disabled = false;
            btnRunAudit.querySelector("span").textContent = "Audit Evidence & Evaluate";
        }
    }

    // 6. Pipeline Animation
    async function animatePipeline() {
        const steps = ["step-ingest", "step-extract", "step-rag", "step-score", "step-gate"];
        for (let i = 0; i < steps.length; i++) {
            const step = document.getElementById(steps[i]);
            step.classList.add("active");
            addLog(`Pipeline Stage ${i + 1}: ${step.textContent.trim()}...`);
            await new Promise(r => setTimeout(r, 120));
        }
    }

    function completePipeline() {
        const steps = ["step-ingest", "step-extract", "step-rag", "step-score", "step-gate"];
        steps.forEach(id => {
            const s = document.getElementById(id);
            s.classList.remove("active");
            s.classList.add("done");
        });
    }

    function resetPipelineSteps() {
        const steps = ["step-ingest", "step-extract", "step-rag", "step-score", "step-gate"];
        steps.forEach(id => {
            const s = document.getElementById(id);
            s.className = "pipe-step";
        });
    }

    function addLog(msg) {
        const entry = document.createElement("div");
        entry.className = "log-entry";
        if (msg.includes("GATE") || msg.includes("Decision")) entry.className += " gate";
        entry.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
        auditLogBox.appendChild(entry);
        auditLogBox.scrollTop = auditLogBox.scrollHeight;
    }

    // 7. Render Complete Audit Results
    function renderAuditResults(data) {
        activeCitations = {};

        // Status Banner
        const status = data.decision_status;
        statusTitle.textContent = status.replace(/_/g, " ");
        decisionPill.textContent = status.replace(/_/g, " ");
        
        // Remove old status classes
        decisionPill.className = "decision-pill";
        if (status === "SUPPORTED") {
            decisionPill.classList.add("status-supported");
            statusSummary.textContent = "The clinical findings are corroborated by authoritative guidelines with no unresolved contradictions.";
        } else if (status === "CONFLICTING") {
            decisionPill.classList.add("status-conflicting");
            statusSummary.textContent = "Authoritative sources disagree on clinical diagnostic criteria, target thresholds, or management recommendations.";
        } else if (status === "ADDITIONAL_INFORMATION_REQUIRED") {
            decisionPill.classList.add("status-missing");
            statusSummary.textContent = "Critical clinical context (e.g. repeat measurement, symptoms, medications) is missing. An isolated finding cannot establish a diagnosis.";
        } else if (status === "QUESTIONABLE") {
            decisionPill.classList.add("status-questionable");
            statusSummary.textContent = "Evidence originates from unverified, commercial, or low-authority sources that fail clinical rigor standards.";
        } else {
            decisionPill.classList.add("status-inconclusive");
            statusSummary.textContent = "Available evidence is insufficient to justify a reliable clinical conclusion without licensed medical consultation.";
        }

        // Human Review Badge
        if (data.human_review_required) {
            humanReviewBadge.style.display = "inline-flex";
        } else {
            humanReviewBadge.style.display = "none";
        }

        // Quality Score Breakdown
        const score = data.evidence_quality_score || 0;
        compositeScoreNum.textContent = score.toFixed(0);
        compositeTier.textContent = data.score_breakdown?.quality_tier || (score >= 85 ? "HIGH" : score >= 65 ? "MODERATE" : "LOW");
        
        const b = data.score_breakdown || {};
        barAuth.style.width = `${b.authority_pct || 0}%`;
        barRel.style.width = `${b.relevance_pct || 0}%`;
        barRec.style.width = `${b.recency_pct || 0}%`;
        barMeth.style.width = `${b.methodology_pct || 0}%`;
        barTrac.style.width = `${b.traceability_pct || 0}%`;

        dimAuth.textContent = `${b.authority_pct || 0}%`;
        dimRel.textContent = `${b.relevance_pct || 0}%`;
        dimRec.textContent = `${b.recency_pct || 0}%`;
        dimMeth.textContent = `${b.methodology_pct || 0}%`;
        dimTrac.textContent = `${b.traceability_pct || 0}%`;

        // Findings Grid
        findingsGrid.innerHTML = "";
        if (data.observations && data.observations.length > 0) {
            data.observations.forEach(o => {
                const card = document.createElement("div");
                card.className = "finding-card";
                
                let valStr = "";
                if (typeof o.value === "object" && o.value !== null) {
                    valStr = o.value.formatted || JSON.stringify(o.value);
                } else {
                    valStr = `${o.value} ${o.unit || ''}`;
                }

                card.innerHTML = `
                    <div class="finding-name">${o.name}</div>
                    <div class="finding-val">${valStr}</div>
                    <div class="finding-meta">${o.reference_range ? 'Ref: ' + o.reference_range : 'Source: ' + o.source} (p. ${o.page})</div>
                `;
                findingsGrid.appendChild(card);
            });
        } else {
            findingsGrid.innerHTML = '<div class="empty-state">No structured quantitative observations detected.</div>';
        }

        // Explanation Body
        explanationBody.textContent = data.final_explanation || "No explanation generated.";

        // Citations
        citationPillsRow.innerHTML = "";
        const allEv = [...(data.supporting_evidence || []), ...(data.conflicting_evidence || []), ...(data.questionable_evidence || [])];
        allEv.forEach(e => {
            activeCitations[e.evidence_id] = e;
            const pill = document.createElement("button");
            pill.className = "citation-pill";
            pill.textContent = `[${e.evidence_id}] ${e.source_name}`;
            pill.addEventListener("click", () => openCitationModal(e.evidence_id));
            citationPillsRow.appendChild(pill);
        });

        // Supporting Evidence Cards — sorted by score descending (highest first)
        supportingList.innerHTML = "";
        if (data.supporting_evidence && data.supporting_evidence.length > 0) {
            const sortedSupporting = [...data.supporting_evidence]
                .sort((a, b) => b.evidence_score - a.evidence_score);
            sortedSupporting.forEach(e => {
                const card = createEvidenceCard(e);
                supportingList.appendChild(card);
            });
        } else {
            supportingList.innerHTML = '<div class="empty-state">No direct supporting evidence found.</div>';
        }

        // Conflicting Evidence Section
        if (data.contradictions && data.contradictions.length > 0) {
            conflictSection.style.display = "block";
            conflictContainer.innerHTML = "";
            data.contradictions.forEach(c => {
                conflictContainer.innerHTML += `
                    <div class="conflict-col">
                        <div class="conflict-header">[${c.source_a_id}] ${c.source_a_name}</div>
                        <p class="ev-excerpt">${c.source_a_claim}</p>
                    </div>
                    <div class="conflict-col">
                        <div class="conflict-header">[${c.source_b_id}] ${c.source_b_name}</div>
                        <p class="ev-excerpt">${c.source_b_claim}</p>
                    </div>
                    <div class="conflict-reason-box">
                        <strong>Reason for Guideline Divergence:</strong> ${c.difference_reason}
                    </div>
                `;
            });
        } else {
            conflictSection.style.display = "none";
        }

        // Missing Information Section
        if (data.missing_information && data.missing_information.length > 0) {
            missingSection.style.display = "block";
            missingList.innerHTML = "";
            data.missing_information.forEach(m => {
                const item = document.createElement("div");
                item.className = "missing-item";
                const catClass = m.category.toLowerCase();
                item.innerHTML = `
                    <span class="missing-tag ${catClass}">${m.category}</span>
                    <div class="missing-desc">
                        <strong>${m.item}</strong>
                        <span>${m.clinical_reason}</span>
                    </div>
                `;
                missingList.appendChild(item);
            });
        } else {
            missingSection.style.display = "none";
        }

        // Questionable Evidence Section — sorted by score descending (highest first)
        if (data.questionable_evidence && data.questionable_evidence.length > 0) {
            questionableSection.style.display = "block";
            questionableList.innerHTML = "";
            const sortedQuestionable = [...data.questionable_evidence]
                .sort((a, b) => b.evidence_score - a.evidence_score);
            sortedQuestionable.forEach(q => {
                const card = createEvidenceCard(q, true);
                questionableList.appendChild(card);
            });
        } else {
            questionableSection.style.display = "none";
        }

        // Render Evidence Map / Graph SVG
        renderEvidenceGraph(data.graph_nodes || [], data.graph_links || []);

        addLog(`Audit completed. Decision: ${status} | Score: ${score.toFixed(1)}/100`);
    }

    // Truncates `text` at the nearest sentence end (.!?) at or after `limit` chars.
    // Returns { preview, full, isTruncated } — never cuts mid-sentence.
    function truncateText(text, limit = 150) {
        if (!text || text.length <= limit) {
            return { preview: text, full: text, isTruncated: false };
        }
        // Start scanning for a sentence-ending punctuation at/after the limit
        const sentenceEnd = /[.!?]/g;
        sentenceEnd.lastIndex = limit;
        const match = sentenceEnd.exec(text);
        const cutAt = match ? match.index + 1 : text.length;
        return {
            preview: text.slice(0, cutAt).trim(),
            full: text,
            isTruncated: cutAt < text.length
        };
    }

    function createEvidenceCard(e, isQuestionable = false) {
        const card = document.createElement("div");
        card.className = "ev-card";
        const { preview, full, isTruncated } = truncateText(e.text);
        card.innerHTML = `
            <div class="ev-top">
                <span class="ev-id-badge">[${e.evidence_id}] ${e.source_name}</span>
                <span class="ev-score-badge">Score: ${e.evidence_score.toFixed(0)}/100</span>
            </div>
            <div class="ev-title">${e.title}</div>
            <div class="ev-excerpt">
                <span class="ev-excerpt-text">${preview}</span>${isTruncated ? ' <a href="#" class="ev-read-more">Read more</a>' : ''}
            </div>
            <div class="ev-footer">
                <span>Tier ${e.authority_tier} • Pub: ${e.publication_date || 'N/A'}</span>
                ${e.url ? `<a href="${e.url}" target="_blank" rel="noopener">Provenance Source &rarr;</a>` : ''}
            </div>
        `;
        if (isTruncated) {
            const link = card.querySelector(".ev-read-more");
            const span = card.querySelector(".ev-excerpt-text");
            let expanded = false;
            link.addEventListener("click", (evt) => {
                evt.preventDefault();
                expanded = !expanded;
                span.innerHTML = expanded ? full : preview;
                link.textContent = expanded ? "Read less" : "Read more";
            });
        }
        return card;
    }

    // 8. Citation Modal Functions
    function openCitationModal(evId) {
        const ev = activeCitations[evId];
        if (!ev) return;

        modalEvId.textContent = `Citation [${ev.evidence_id}]`;
        modalSourceTitle.textContent = ev.title;
        modalSourceName.textContent = ev.source_name;
        modalScore.textContent = `${ev.evidence_score.toFixed(1)}/100 (${ev.quality_label || 'HIGH'})`;
        modalDate.textContent = ev.publication_date || 'N/A';
        modalTier.textContent = `Tier ${ev.authority_tier} (${ev.source_type || 'Authoritative'})`;
        modalExcerpt.textContent = ev.text;
        
        if (ev.url) {
            modalUrl.href = ev.url;
            modalUrl.style.display = "inline";
        } else {
            modalUrl.style.display = "none";
        }

        citationModal.style.display = "flex";
    }

    modalCloseBtn.addEventListener("click", () => {
        citationModal.style.display = "none";
    });

    citationModal.addEventListener("click", (e) => {
        if (e.target === citationModal) {
            citationModal.style.display = "none";
        }
    });

    // 9. Simple Interactive SVG Evidence Graph Renderer
    function renderEvidenceGraph(nodes, links) {
        evidenceSvg.innerHTML = "";
        if (!nodes.length) return;

        const width = evidenceSvg.clientWidth || 600;
        const height = 260;
        const centerX = width / 2;
        const centerY = height / 2;

        // Position nodes in a radial layout
        const nodePositions = {};
        const rootNode = nodes.find(n => n.id === "CLAIM-ROOT") || nodes[0];
        nodePositions[rootNode.id] = { x: centerX, y: centerY };

        const otherNodes = nodes.filter(n => n.id !== rootNode.id);
        const radius = Math.min(width, height) * 0.38;
        const angleStep = (2 * Math.PI) / Math.max(1, otherNodes.length);

        otherNodes.forEach((node, i) => {
            const angle = i * angleStep;
            nodePositions[node.id] = {
                x: centerX + radius * Math.cos(angle),
                y: centerY + radius * Math.sin(angle)
            };
        });

        // Draw Links
        links.forEach(link => {
            const p1 = nodePositions[link.source];
            const p2 = nodePositions[link.target];
            if (p1 && p2) {
                const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
                line.setAttribute("x1", p1.x);
                line.setAttribute("y1", p1.y);
                line.setAttribute("x2", p2.x);
                line.setAttribute("y2", p2.y);
                
                let strokeColor = "#3b82f6";
                if (link.relation === "CONTRADICTS") strokeColor = "#f59e0b";
                if (link.relation === "QUESTIONS") strokeColor = "#ef4444";
                if (link.relation === "DERIVED_FROM") strokeColor = "#94a3b8";

                line.setAttribute("stroke", strokeColor);
                line.setAttribute("stroke-width", "1.8");
                line.setAttribute("stroke-dasharray", link.relation === "CONTRADICTS" ? "4,4" : "none");
                evidenceSvg.appendChild(line);
            }
        });

        // Draw Nodes
        nodes.forEach(node => {
            const pos = nodePositions[node.id];
            if (!pos) return;

            const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
            g.setAttribute("transform", `translate(${pos.x}, ${pos.y})`);
            g.style.cursor = "pointer";

            const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            circle.setAttribute("r", node.id === "CLAIM-ROOT" ? "22" : "14");
            
            let fill = "#1e293b";
            let stroke = "#3b82f6";
            if (node.status === "SUPPORTED" || node.status === "SUPPORTING") stroke = "#10b981";
            if (node.status === "CONFLICTING") stroke = "#f59e0b";
            if (node.status === "QUESTIONABLE") stroke = "#ef4444";

            circle.setAttribute("fill", fill);
            circle.setAttribute("stroke", stroke);
            circle.setAttribute("stroke-width", "2.5");
            g.appendChild(circle);

            const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
            text.setAttribute("y", node.id === "CLAIM-ROOT" ? "34" : "24");
            text.setAttribute("text-anchor", "middle");
            text.setAttribute("fill", "#cbd5e1");
            text.setAttribute("font-size", "10px");
            text.setAttribute("font-family", "JetBrains Mono, monospace");
            text.textContent = node.label.length > 18 ? node.label.substring(0, 16) + '..' : node.label;
            g.appendChild(text);

            evidenceSvg.appendChild(g);
        });
    }

    // Start App
    loadHealth();
    loadFixtures();
});
