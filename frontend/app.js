"use strict";

/* =========================================================
   ARCHLENS — MAIN FRONTEND APPLICATION
   Features:
   1. Backend status
   2. Repository selection
   3. Architecture graph
   4. Component details
   5. Repository-aware RAG Q&A
   6. Change-impact analysis
   7. Architecture Intelligence Center
========================================================= */

const API_BASE_URL = "http://127.0.0.1:8000";

let architectureData = null;
let cy = null;
let selectedComponent = null;
let currentRepository = null;


/* =========================================================
   HELPERS
========================================================= */

function getElement(...ids) {
    for (const id of ids) {
        const element = document.getElementById(id);

        if (element) {
            return element;
        }
    }

    return null;
}


function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = String(value ?? "");
    return div.innerHTML;
}


function setText(ids, value) {
    const element = getElement(...ids);

    if (element) {
        element.textContent = String(value ?? "");
    }
}


function setStatus(message) {
    const element = getElement("dashboardStatus");

    if (element) {
        element.textContent = message;
    }
}


async function apiRequest(path, options = {}) {
    const response = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers: {
            ...(options.body ? { "Content-Type": "application/json" } : {}),
            ...(options.headers || {})
        }
    });

    const contentType = response.headers.get("content-type") || "";

    let data;

    if (contentType.includes("application/json")) {
        data = await response.json();
    } else {
        data = await response.text();
    }

    if (!response.ok) {
        const message =
            typeof data === "object"
                ? data.detail || data.message
                : data;

        throw new Error(message || `HTTP ${response.status}`);
    }

    return data;
}


/* =========================================================
   BACKEND STATUS
========================================================= */

async function checkBackend() {
    const status = getElement("status");

    try {
        const data = await apiRequest("/");

        if (status) {
            status.innerHTML = `
                <span class="status-dot"></span>
                Backend Connected
            `;
        }

        console.log("Backend:", data);

    } catch (error) {
        console.error("Backend connection failed:", error);

        if (status) {
            status.innerHTML = `
                <span class="status-dot"
                      style="background:#ef4444"></span>
                Backend Offline
            `;
        }
    }
}


/* =========================================================
   REPOSITORIES
========================================================= */

async function loadRepositories() {
    const select = getElement("repository");

    if (!select) {
        console.warn("Repository dropdown not found.");
        return;
    }

    try {
        const data = await apiRequest("/repositories");

        const repositories = Array.isArray(data)
            ? data
            : data.repositories || [];

        const previousValue = select.value;

        select.replaceChildren();

        repositories.forEach((item) => {
            const repository =
                typeof item === "string"
                    ? item
                    : item.name || item.repository || item.id;

            if (!repository) {
                return;
            }

            const option = document.createElement("option");
            option.value = repository;
            option.textContent = repository;

            select.appendChild(option);
        });

        if (
            previousValue &&
            repositories.some((item) =>
                (typeof item === "string"
                    ? item
                    : item.name || item.repository || item.id
                ) === previousValue
            )
        ) {
            select.value = previousValue;
        }

        console.log("Repositories:", repositories);

        if (select.value) {
            await loadArchitecture();
        }

    } catch (error) {
        console.error("Could not load repositories:", error);
    }
}


/* =========================================================
   LOAD ARCHITECTURE
========================================================= */

async function loadArchitecture() {
    const select = getElement("repository");
    const repository = select?.value;

    const graphContainer = getElement("cy", "architectureGraph");
    const summaryContainer = getElement("architectureSummary");

    if (!repository) {
        console.warn("Select a repository first.");

        if (graphContainer) {
            graphContainer.textContent = "Please select a repository.";
        }

        return;
    }

    currentRepository = repository;

    console.log("Selected repository:", repository);

    if (graphContainer && !getElement("cy")) {
        graphContainer.textContent = "Loading architecture...";
    }

    try {
        const url =
            `/architecture/${encodeURIComponent(repository)}`;

        console.log("Architecture URL:", `${API_BASE_URL}${url}`);

        const data = await apiRequest(url);

        /*
         * Support both response formats:
         *
         * { repository: "...", graph: { nodes: [], edges: [] } }
         *
         * and:
         *
         * { nodes: [], edges: [] }
         */

        const graph = data.graph || data;

        if (!Array.isArray(graph.nodes) ||
            !Array.isArray(graph.edges)) {
            throw new Error(
                "The architecture response must contain nodes and edges."
            );
        }

        architectureData = {
            ...graph,
            nodes: graph.nodes,
            edges: graph.edges
        };

        console.log("Architecture data:", data);
        console.log("Nodes:", architectureData.nodes);
        console.log("Edges:", architectureData.edges);

        displaySummary(architectureData);
        displayArchitecture(architectureData);

        // Update the dashboard for the selected repository.
        await loadArchitectureDashboard();

    } catch (error) {
        console.error("Architecture loading failed:", error);

        if (graphContainer && !getElement("cy")) {
            graphContainer.textContent =
                `Could not load architecture: ${error.message}`;
        }

        if (summaryContainer) {
            summaryContainer.textContent =
                "Could not load architecture summary.";
        }

        setStatus(`Architecture loading failed: ${error.message}`);
    }
}


/* =========================================================
   SUMMARY
========================================================= */

function displaySummary(graph) {
    const container = getElement("architectureSummary");

    if (!container) {
        return;
    }

    const nodes = graph.nodes || [];
    const edges = graph.edges || [];

    const countType = (type) =>
        nodes.filter(
            (node) =>
                String(node.type || "").toLowerCase() === type
        ).length;

    const metrics = [
        ["Files", countType("file")],
        ["Modules", countType("module")],
        ["Classes", countType("class")],
        ["Functions", countType("function")],
        ["Relationships", edges.length]
    ];

    container.replaceChildren();

    metrics.forEach(([label, count]) => {
        const card = document.createElement("div");
        card.className = "summary-card";

        const strong = document.createElement("strong");
        strong.textContent = String(count);

        const span = document.createElement("span");
        span.textContent = label;

        card.append(strong, span);
        container.appendChild(card);
    });
}


/* =========================================================
   ARCHITECTURE GRAPH — CYTOSCAPE
========================================================= */

function displayArchitecture(graph) {
    /*
     * Your existing HTML uses the Cytoscape container #cy.
     * architectureGraph is retained as a fallback for older HTML.
     */

    const container = getElement("cy", "architectureGraph");

    if (!container) {
        console.error(
            "Graph container not found. Expected id='cy' or id='architectureGraph'."
        );
        return;
    }

    const nodes = graph.nodes || [];
    const edges = graph.edges || [];
    // Update architecture statistics.
    const nodeCountElement = document.getElementById("nodeCount");
    const edgeCountElement = document.getElementById("edgeCount");
    if (nodeCountElement) {
        nodeCountElement.textContent = nodes.length;
    }

    if (edgeCountElement) {
       edgeCountElement.textContent = edges.length;
    }


    if (nodes.length === 0) {
        container.textContent = "No architecture data found.";
        return;
    }

    // If Cytoscape is unavailable, use a simple component list.
    if (typeof window.cytoscape !== "function") {
        console.error("Cytoscape library is not loaded.");

        renderFallbackComponentList(container, nodes);
        return;
    }

    const elements = [];

    nodes.forEach((node) => {
        if (node.id === undefined || node.id === null) {
            return;
        }

        elements.push({
            group: "nodes",
            data: {
                id: String(node.id),
                label: String(node.label || node.name || node.id),
                type: String(node.type || "unknown"),
                file: String(
                    node.file ||
                    node.path ||
                    node.file_path ||
                    ""
                ),
                original: node
            }
        });
    });

    const validIds = new Set(
        elements
            .filter((element) => element.group === "nodes")
            .map((element) => element.data.id)
    );

    edges.forEach((edge, index) => {
        const source = String(edge.source ?? edge.from ?? "");
        const target = String(edge.target ?? edge.to ?? "");

        if (!validIds.has(source) || !validIds.has(target)) {
            return;
        }

        elements.push({
            group: "edges",
            data: {
                id: `edge-${index}-${source}-${target}`,
                source,
                target,
                label: String(
                    edge.relationship ||
                    edge.type ||
                    edge.label ||
                    "depends on"
                )
            }
        });
    });

    // Destroy only the previous Cytoscape instance.
    if (cy) {
        cy.destroy();
        cy = null;
    }

    container.replaceChildren();

    cy = window.cytoscape({
        container,

        elements,
                   style: [
            {
                selector: "node",
                style: {
                    "background-color": function (element) {
                        const type = element.data("type");

                        if (type === "file") return "#2563eb";
                        if (type === "module") return "#7c3aed";
                        if (type === "class") return "#059669";
                        if (type === "function") return "#ea580c";
                        if (type === "function_reference") return "#64748b";

                        return "#475569";
                    },

                    "label": "data(label)",
                    "color": "#111827",
                    "font-size": 12,
                    "font-weight": "bold",

                    "text-valign": "bottom",
                    "text-halign": "center",
                    "text-margin-y": 8,

                    "width": 45,
                    "height": 45,

                    "border-width": 2,
                    "border-color": "#ffffff"
                }
            },

            {
                selector: "edge",
                style: {
                    "width": 2,
                    "line-color": "#94a3b8",
                    "target-arrow-color": "#64748b",
                    "target-arrow-shape": "triangle",
                    "curve-style": "bezier",

                    "label": "data(label)",
                    "font-size": 10,
                    "color": "#334155",

                    "text-background-color": "#ffffff",
                    "text-background-opacity": 1,
                    "text-background-padding": 3
                }
            },

            {
                selector: "node:selected",
                style: {
                    "background-color": "#facc15",
                    "border-color": "#f59e0b",
                    "border-width": 4
                }
            },

            {
                selector: ".impact-selected",
                style: {
                    "border-color": "#facc15",
                    "border-width": 6
                }
            },

            {
                selector: ".impact-affected",
                style: {
                    "border-color": "#ef4444",
                    "border-width": 5
                }
            },

            {
                selector: "edge:selected",
                style: {
                    "line-color": "#2563eb",
                    "target-arrow-color": "#2563eb",
                    "width": 4
                }
            }
        ],

        layout: {
            name: "breadthfirst",
            directed: true,
            animate: true,
            fit: true,
            spacingFactor: 1.5,
            padding: 80,
            nodeRepulsion: 8000,
            idealEdgeLength: 150



        },

        minZoom: 0.1,
        maxZoom: 3,
        wheelSensitivity: 0.2
    });

    cy.on("tap", "node", (event) => {
        const data = event.target.data();

        const original = data.original || {};

        selectedComponent = {
            id: String(data.id),
            label: data.label,
            type: data.type,
            file: data.file,
            original
        };

        showComponentDetails(original.id !== undefined
            ? original
            : {
                id: data.id,
                label: data.label,
                type: data.type,
                file: data.file
            }
        );

        const impactButton = getElement("impactButton");

        if (impactButton) {
            impactButton.disabled = false;
        }
    });

    cy.on("tap", (event) => {
        if (event.target === cy) {
            selectedComponent = null;
        }
    });

    // Allow Cytoscape to size itself correctly.
    requestAnimationFrame(() => {
        if (cy) {
            cy.resize();
            cy.fit(undefined, 40);
        }
    });
}


function renderFallbackComponentList(container, nodes) {
    container.replaceChildren();

    nodes.forEach((node) => {
        const button = document.createElement("button");

        button.type = "button";
        button.className = "graph-node";
        button.textContent =
            `${node.label || node.id} (${node.type || "unknown"})`;

        button.addEventListener("click", () => {
            selectedComponent = node;
            showComponentDetails(node);
        });

        container.appendChild(button);
    });
}


/* =========================================================
   COMPONENT DETAILS
========================================================= */

function showComponentDetails(node) {
    const container = getElement("details", "componentDetails");

    if (!container || !architectureData) {
        return;
    }

    const nodeId = String(node.id);
    const nodes = architectureData.nodes || [];
    const edges = architectureData.edges || [];

    const nodeMap = new Map(
        nodes.map((item) => [String(item.id), item])
    );

    const relationships = edges.filter(
        (edge) =>
            String(edge.source ?? edge.from) === nodeId ||
            String(edge.target ?? edge.to) === nodeId
    );

    container.replaceChildren();

    const title = document.createElement("h3");
    title.textContent = node.label || node.name || node.id;

    const type = document.createElement("p");
    type.textContent = `Type: ${node.type || "unknown"}`;

    container.append(title, type);

    const filePath =
        node.file || node.path || node.file_path || "";

    if (filePath) {
        const file = document.createElement("p");
        file.textContent = `File: ${filePath}`;
        container.appendChild(file);
    }

    const heading = document.createElement("h4");
    heading.textContent = "Relationships";
    container.appendChild(heading);

    if (relationships.length === 0) {
        const empty = document.createElement("p");
        empty.textContent = "No relationships found.";
        container.appendChild(empty);
        return;
    }

    relationships.forEach((edge) => {
        const source = String(edge.source ?? edge.from);
        const target = String(edge.target ?? edge.to);

        const isSource = source === nodeId;
        const otherId = isSource ? target : source;
        const otherNode = nodeMap.get(otherId);

        const row = document.createElement("div");
        row.className = "relationship";

        const relationship = document.createElement("span");
        relationship.className = "relationship-type";
        relationship.textContent =
            edge.relationship || edge.type || edge.label || "depends on";

        const direction = document.createElement("span");
        direction.textContent = isSource ? " → " : " ← ";

        const name = document.createElement("strong");
        name.textContent = otherNode
            ? otherNode.label || otherNode.name || otherId
            : otherId;

        row.append(relationship, direction, name);
        container.appendChild(row);
    });
}


/* =========================================================
   REPOSITORY-AWARE AI Q&A
========================================================= */

async function askArchLens() {
    const questionInput = getElement("question");
    const answerContainer = getElement("answer");
    const answerSection = getElement("answerSection");
    const sourcesContainer = getElement("sources");
    const button = getElement("askButton");
    const repositorySelect = getElement("repository");

    if (!questionInput || !answerContainer || !button) {
        console.error("One or more Q&A HTML elements are missing.");
        return;
    }

    const question = questionInput.value.trim();
    const repository = repositorySelect?.value || currentRepository;

    if (!question) {
        alert("Please enter a question.");
        return;
    }

    if (!repository) {
        alert("Please select a repository first.");
        return;
    }

    button.disabled = true;
    button.textContent = "Thinking...";

    if (answerSection) {
        answerSection.classList.remove("hidden");
        answerSection.style.display = "";
    }

    answerContainer.textContent = "Analyzing repository...";

    if (sourcesContainer) {
        sourcesContainer.replaceChildren();
    }

    try {
        const data = await apiRequest("/ask", {
            method: "POST",
            body: JSON.stringify({
                question,
                repository
            })
        });

        answerContainer.textContent =
            data.answer || "No answer returned.";

        if (sourcesContainer) {
            const sources = data.sources || [];

            if (sources.length === 0) {
                const empty = document.createElement("span");
                empty.className = "empty";
                empty.textContent = "No sources available.";
                sourcesContainer.appendChild(empty);
            } else {
                sources.forEach((source) => {
                    const span = document.createElement("span");
                    span.className = "source";
                    span.textContent =
                        typeof source === "string"
                            ? source
                            : source.file || source.source || JSON.stringify(source);

                    sourcesContainer.appendChild(span);
                });
            }
        }

    } catch (error) {
        console.error("ArchLens Q&A error:", error);

        answerContainer.textContent =
            `Could not get an answer: ${error.message}`;

    } finally {
        button.disabled = false;
        button.textContent = "Ask ArchLens";
    }
}


/* =========================================================
   CHANGE-IMPACT ANALYSIS
========================================================= */

async function runImpactAnalysis() {
    const repositorySelect = getElement("repository");
    const button = getElement("impactButton");
    const reportContainer = getElement("impactReport");

    const repository = repositorySelect?.value || currentRepository;

    if (!repository) {
        alert("Please select a repository.");
        return;
    }

    if (!selectedComponent || !selectedComponent.id) {
        alert("Select a component in the architecture graph first.");
        return;
    }

    if (button) {
        button.disabled = true;
        button.textContent = "Analyzing...";
    }

    if (reportContainer) {
        reportContainer.textContent = "Analyzing change impact...";
    }

    try {
        const data = await apiRequest("/impact-analysis", {
            method: "POST",
            body: JSON.stringify({
                repository,
                component: selectedComponent.id,
                max_depth: 10
            })
        });

        renderImpactReport(data);

    } catch (error) {
        console.error("Change-impact analysis failed:", error);

        if (reportContainer) {
            reportContainer.textContent =
                `Change-impact analysis failed: ${error.message}`;
        }

    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = "Analyze Change Impact";
        }
    }
}


function renderImpactReport(data) {
    const container = getElement("impactReport");

    if (!container) {
        console.warn("Impact report container not found.");
        return;
    }

    container.replaceChildren();

    const summary = data.summary || {};

    const title = document.createElement("h3");
    title.textContent =
        `Impact Analysis: ${data.selected_component?.label || selectedComponent?.label || "Selected component"}`;

    container.appendChild(title);

    const metrics = [
        ["Overall Risk", summary.overall_risk ?? "Unknown"],
        ["Impact Score", summary.impact_score ?? 0],
        ["Direct Dependencies", summary.direct_dependencies ?? 0],
        ["Indirect Dependencies", summary.indirect_dependencies ?? 0]
    ];

    const metricsContainer = document.createElement("div");
    metricsContainer.className = "impact-summary-cards";

    metrics.forEach(([label, value]) => {
        const card = document.createElement("div");
        card.className = "summary-card";

        const strong = document.createElement("strong");
        strong.textContent = String(value);

        const span = document.createElement("span");
        span.textContent = label;

        card.append(strong, span);
        metricsContainer.appendChild(card);
    });

    container.appendChild(metricsContainer);

    const impacted = data.impacted_components || [];

    const heading = document.createElement("h3");
    heading.textContent = `Impacted Components (${impacted.length})`;
    container.appendChild(heading);

    if (impacted.length === 0) {
        const empty = document.createElement("p");
        empty.textContent = "No impacted components were detected.";
        container.appendChild(empty);
    }

    impacted.forEach((component) => {
        const card = document.createElement("article");
        card.className = "finding-card";

        const name = document.createElement("h4");
        name.textContent =
            component.label || component.id || "Unknown component";

        const type = document.createElement("p");
        type.textContent =
            `Type: ${component.type || "unknown"} | ` +
            `Direction: ${component.direction || "not specified"}`;

        const pathData = component.dependency_path;
        const path = Array.isArray(pathData)
            ? pathData
            : Array.isArray(pathData?.nodes)
                ? pathData.nodes
                : [];

        card.append(name, type);

        if (path.length > 0) {
            const pathLabel = document.createElement("p");
            pathLabel.textContent = "Dependency path:";
            card.appendChild(pathLabel);

            const pathContainer = document.createElement("div");
            pathContainer.className = "finding-components";

            path.forEach((part) => {
                const chip = document.createElement("span");
                chip.className = "finding-component";
                chip.textContent =
                    typeof part === "object"
                        ? part.label || part.id || "Component"
                        : String(part);

                pathContainer.appendChild(chip);
            });

            card.appendChild(pathContainer);
        }

        const focusButton = document.createElement("button");
        focusButton.type = "button";
        focusButton.textContent = "Focus in Graph";

        focusButton.addEventListener("click", () => {
            focusGraphComponent(component.id);
        });

        card.appendChild(focusButton);
        container.appendChild(card);
    });

    const limitations = data.limitations || [];

    if (limitations.length > 0) {
        const note = document.createElement("p");
        note.textContent =
            "Limitations: " +
            limitations.map((item) =>
                typeof item === "string" ? item : JSON.stringify(item)
            ).join(" ");
        container.appendChild(note);
    }
}


function focusGraphComponent(componentId) {
    if (!cy || componentId === undefined || componentId === null) {
        return;
    }

    const node = cy.getElementById(String(componentId));

    if (node.empty()) {
        console.warn("Component not found in graph:", componentId);
        return;
    }

    cy.elements().removeClass("impact-affected");
    node.addClass("impact-affected");

    cy.animate({
        fit: {
            eles: node,
            padding: 100
        },
        duration: 500
    });
}


/* =========================================================
   ARCHITECTURE INTELLIGENCE CENTER
========================================================= */

async function loadArchitectureDashboard() {
    const repositorySelect = getElement("repository");
    const refreshButton = getElement("refreshDashboard");
    const statusElement = getElement("dashboardStatus");

    if (!repositorySelect || !statusElement) {
        console.warn("Dashboard controls not found.");
        return;
    }

    const repository = repositorySelect.value;

    if (!repository) {
        statusElement.textContent = "Please select a repository first.";
        return;
    }

    if (refreshButton) {
        refreshButton.disabled = true;
        refreshButton.textContent = "Analyzing...";
    }

    statusElement.textContent = "Analyzing repository architecture...";

    try {
        const data = await apiRequest(
            `/dashboard/${encodeURIComponent(repository)}`
        );

        renderArchitectureDashboard(data);

        statusElement.textContent =
            `Analysis completed for ${data.repository}. ` +
            `${data.summary?.total_findings ?? 0} finding(s) detected.`;

        console.log("Dashboard data:", data);

    } catch (error) {
        console.error("Dashboard loading error:", error);

        statusElement.textContent =
            `Could not load dashboard: ${error.message}`;

    } finally {
        if (refreshButton) {
            refreshButton.disabled = false;
            refreshButton.textContent = "↻ Refresh Analysis";
        }
    }
}


function renderArchitectureDashboard(data) {
    const metrics = data.metrics || {};
    const health = data.health || {};
    const summary = data.summary || {};

    setText(
        ["healthScore"],
        Number.isFinite(Number(health.score)) ? health.score : "--"
    );

    setText(["healthLabel"], health.label || "Not available");

    const progress = getElement("healthProgress");

    if (progress) {
        const score = Number(health.score);

        progress.style.width = Number.isFinite(score)
            ? `${Math.max(0, Math.min(100, score))}%`
            : "0%";
    }

    setText(["totalComponents"], metrics.total_components ?? 0);
    setText(["totalRelationships"], metrics.total_relationships ?? 0);

    setText(
        ["circularDependencies"],
        summary.circular_dependency_groups ?? 0
    );

    setText(["totalFindings"], summary.total_findings ?? 0);

    setText(["criticalCount"], summary.critical ?? 0);
    setText(["highCount"], summary.high ?? 0);
    setText(["mediumCount"], summary.medium ?? 0);
    setText(["lowCount"], summary.low ?? 0);

    renderLanguageDistribution(data.language_distribution || {});
    renderArchitectureFindings(data.findings || []);
    renderConnectedComponents(data.top_connected_components || []);
}


function renderLanguageDistribution(distribution) {
    const container = getElement("languageDistribution");

    if (!container) {
        return;
    }

    container.replaceChildren();

    const entries = Object.entries(distribution)
        .sort((a, b) => Number(b[1]) - Number(a[1]));

    const total = entries.reduce(
        (sum, [, count]) => sum + Number(count || 0),
        0
    );

    if (entries.length === 0) {
        const empty = document.createElement("p");
        empty.className = "dashboard-empty";
        empty.textContent = "No language information available.";
        container.appendChild(empty);
        return;
    }

    entries.forEach(([language, count]) => {
        const numericCount = Number(count) || 0;

        const percentage = total > 0
            ? numericCount / total * 100
            : 0;

        const row = document.createElement("div");
        row.className = "language-row";

        const name = document.createElement("span");
        name.className = "language-name";
        name.textContent = language;

        const track = document.createElement("div");
        track.className = "language-track";

        const bar = document.createElement("div");
        bar.className = "language-bar";
        bar.style.width = `${percentage}%`;

        track.appendChild(bar);

        const countLabel = document.createElement("span");
        countLabel.className = "language-count";
        countLabel.textContent = String(numericCount);

        row.append(name, track, countLabel);
        container.appendChild(row);
    });
}


function renderArchitectureFindings(findings) {
    const container = getElement("architectureFindings");

    if (!container) {
        return;
    }

    container.replaceChildren();

    if (findings.length === 0) {
        const empty = document.createElement("p");
        empty.className = "dashboard-empty";
        empty.textContent =
            "No findings were detected by the current architecture rules.";

        container.appendChild(empty);
        return;
    }

    findings.forEach((finding) => {
        const card = document.createElement("article");
        card.className = "finding-card";

        const header = document.createElement("div");
        header.className = "finding-header";

        const rule = document.createElement("span");
        rule.className = "finding-rule";
        rule.textContent = finding.rule_id || "RULE";

        const title = document.createElement("h4");
        title.textContent = finding.title || "Architecture finding";

        const severityValue = String(
            finding.severity || "low"
        ).toLowerCase();

        const severity = document.createElement("span");
        severity.className = `finding-severity ${severityValue}`;
        severity.textContent = severityValue;

        header.append(rule, title, severity);

        const description = document.createElement("p");
        description.className = "finding-description";
        description.textContent =
            finding.description || "No description available.";

        card.append(header, description);

        const components = finding.affected_components || [];

        if (components.length > 0) {
            const componentContainer = document.createElement("div");
            componentContainer.className = "finding-components";

            components.forEach((component) => {
                const chip = document.createElement("span");
                chip.className = "finding-component";
                chip.textContent =
                    `${component.label || component.id || "Unknown"} ` +
                    `(${component.type || "component"})`;

                componentContainer.appendChild(chip);
            });

            card.appendChild(componentContainer);
        }

        const recommendation = document.createElement("div");
        recommendation.className = "finding-recommendation";

        const strong = document.createElement("strong");
        strong.textContent = "Recommended action: ";

        recommendation.appendChild(strong);
        recommendation.appendChild(
            document.createTextNode(
                finding.recommendation || "Review this finding."
            )
        );

        card.appendChild(recommendation);
        container.appendChild(card);
    });
}


function renderConnectedComponents(components) {
    const tableBody = getElement("connectedComponentsTable");

    if (!tableBody) {
        return;
    }

    tableBody.replaceChildren();

    if (components.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");

        cell.colSpan = 5;
        cell.textContent = "No connected components available.";

        row.appendChild(cell);
        tableBody.appendChild(row);
        return;
    }

    components.forEach((component) => {
        const row = document.createElement("tr");

        const values = [
            component.label || component.id || "Unknown",
            component.type || "unknown",
            component.incoming_dependencies ?? 0,
            component.outgoing_dependencies ?? 0,
            component.total_connections ?? 0
        ];

        values.forEach((value, index) => {
            const cell = document.createElement("td");
            cell.textContent = String(value);

            if (index === 0) {
                cell.className = "dashboard-component-name";
                cell.title = String(value);
            }

            row.appendChild(cell);
        });

        tableBody.appendChild(row);
    });
}


/* =========================================================
   EVENT LISTENERS
========================================================= */

function initializeArchLens() {
    const askButton = getElement("askButton");
    const loadButton = getElement("loadArchitecture");
    const fitButton = getElement("fitGraph");
    const impactButton = getElement("impactButton");
    const refreshDashboardButton = getElement("refreshDashboard");
    const repositorySelect = getElement("repository");

    if (askButton && !askButton.dataset.listenerAttached) {
        askButton.dataset.listenerAttached = "true";
        askButton.addEventListener("click", askArchLens);
    }

    if (loadButton && !loadButton.dataset.listenerAttached) {
        loadButton.dataset.listenerAttached = "true";
        loadButton.addEventListener("click", loadArchitecture);
    }

    if (fitButton && !fitButton.dataset.listenerAttached) {
        fitButton.dataset.listenerAttached = "true";

        fitButton.addEventListener("click", () => {
            if (cy) {
                cy.fit(undefined, 40);
                cy.center();
            }
        });
    }

    if (impactButton && !impactButton.dataset.listenerAttached) {
        impactButton.dataset.listenerAttached = "true";
        impactButton.addEventListener("click", runImpactAnalysis);
        impactButton.disabled = true;
    }

    if (
        refreshDashboardButton &&
        !refreshDashboardButton.dataset.listenerAttached
    ) {
        refreshDashboardButton.dataset.listenerAttached = "true";

        refreshDashboardButton.addEventListener(
            "click",
            loadArchitectureDashboard
        );
    }

    if (
        repositorySelect &&
        !repositorySelect.dataset.listenerAttached
    ) {
        repositorySelect.dataset.listenerAttached = "true";

        repositorySelect.addEventListener("change", async () => {
            await loadArchitecture();
        });
    }

    // Initialize only once, after the HTML is available.
    checkBackend();
    loadRepositories();
}


if (document.readyState === "loading") {
    document.addEventListener(
        "DOMContentLoaded",
        initializeArchLens,
        { once: true }
    );
} else {
    initializeArchLens();
}
