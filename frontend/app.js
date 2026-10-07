const API_BASE_URL = "http://127.0.0.1:8000";


let architectureData = null;

async function checkBackend() {

    const status =
        document.querySelector(".status");

    try {

        const response = await fetch(
            `${API_BASE_URL}/`
        );

        if (!response.ok) {
            throw new Error("Backend unavailable");
        }

        status.innerHTML = `
            <span class="status-dot"></span>
            Backend Connected
        `;

    } catch (error) {

        status.innerHTML = `
            <span class="status-dot"
                  style="background:#ef4444">
            </span>
            Backend Offline
        `;
    }
}

/* =========================================
   LOAD ARCHITECTURE
========================================= */

async function loadArchitecture() {

    const graphContainer =
        document.getElementById(
            "architectureGraph"
        );

    const summaryContainer =
        document.getElementById(
            "architectureSummary"
        );


    try {

        graphContainer.innerHTML =
            "Loading architecture...";


        const response = await fetch(
            `${API_BASE_URL}/architecture`
        );


        if (!response.ok) {

            throw new Error(
                `HTTP ${response.status}`
            );
        }


        architectureData =
            await response.json();


        displaySummary(
            architectureData
        );


        displayArchitecture(
            architectureData
        );


    } catch (error) {

        console.error(error);


        graphContainer.innerHTML =
            `<p>
                Could not load architecture.
                Make sure FastAPI is running.
            </p>`;


        summaryContainer.innerHTML =
            `<p>
                Backend connection failed.
            </p>`;
    }
}


/* =========================================
   DISPLAY SUMMARY
========================================= */

function displaySummary(graph) {

    const container =
        document.getElementById(
            "architectureSummary"
        );


    const nodes =
        graph.nodes || [];


    const edges =
        graph.edges || [];


    const files =
        nodes.filter(
            node => node.type === "file"
        ).length;


    const modules =
        nodes.filter(
            node => node.type === "module"
        ).length;


    const classes =
        nodes.filter(
            node => node.type === "class"
        ).length;


    const functions =
        nodes.filter(
            node => node.type === "function"
        ).length;


    container.innerHTML = `

        <div class="summary-card">
            <strong>${files}</strong>
            <span>Files</span>
        </div>

        <div class="summary-card">
            <strong>${modules}</strong>
            <span>Modules</span>
        </div>

        <div class="summary-card">
            <strong>${classes}</strong>
            <span>Classes</span>
        </div>

        <div class="summary-card">
            <strong>${functions}</strong>
            <span>Functions</span>
        </div>

        <div class="summary-card">
            <strong>${edges.length}</strong>
            <span>Relationships</span>
        </div>

    `;
}


/* =========================================
   DISPLAY ARCHITECTURE
========================================= */

function displayArchitecture(graph) {

    const container =
        document.getElementById(
            "architectureGraph"
        );


    container.innerHTML = "";


    const nodes =
        graph.nodes || [];


    if (nodes.length === 0) {

        container.innerHTML =
            "<p>No architecture data found.</p>";

        return;
    }


    nodes.forEach(node => {

        const div =
            document.createElement(
                "div"
            );


        div.className =
            "graph-node";


        div.innerHTML = `

            <div class="node-title">
                ${escapeHtml(
                    node.label || node.id
                )}
            </div>

            <div class="node-type">
                ${escapeHtml(
                    node.type || "unknown"
                )}
            </div>

            ${
                node.file
                    ? `
                    <div class="node-file">
                        ${escapeHtml(
                            node.file
                        )}
                    </div>
                    `
                    : ""
            }

        `;


        div.addEventListener(
            "click",
            () => {

                showComponentDetails(
                    node
                );

            }
        );


        container.appendChild(div);

    });
}


/* =========================================
   COMPONENT DETAILS
========================================= */

function showComponentDetails(node) {

    const container =
        document.getElementById(
            "componentDetails"
        );


    if (!architectureData) {

        return;
    }


    const edges =
        architectureData.edges || [];


    const nodes =
        architectureData.nodes || [];


    const nodeMap =
        new Map(
            nodes.map(
                n => [n.id, n]
            )
        );


    const relationships =
        edges.filter(
            edge =>
                edge.source === node.id
                ||
                edge.target === node.id
        );


    let html = `

        <div class="detail-title">
            ${escapeHtml(
                node.label || node.id
            )}
        </div>

        <p>
            <strong>Type:</strong>
            ${escapeHtml(
                node.type || "unknown"
            )}
        </p>

    `;


    if (node.file) {

        html += `

            <p>
                <strong>File:</strong>
                ${escapeHtml(
                    node.file
                )}
            </p>

        `;
    }


    html += `
        <h3>Relationships</h3>
    `;


    if (relationships.length === 0) {

        html += `
            <p class="empty">
                No relationships found.
            </p>
        `;

    } else {

        relationships.forEach(
            edge => {

                const isSource =
                    edge.source === node.id;


                const otherId =
                    isSource
                        ? edge.target
                        : edge.source;


                const otherNode =
                    nodeMap.get(
                        otherId
                    );


                const otherLabel =
                    otherNode
                        ? otherNode.label
                        : otherId;


                html += `

                    <div class="relationship">

                        <span class="relationship-type">
                            ${escapeHtml(
                                edge.relationship
                            )}
                        </span>

                        →

                        <strong>
                            ${escapeHtml(
                                otherLabel
                            )}
                        </strong>

                    </div>

                `;

            }
        );
    }


    container.innerHTML = html;
}


/* =========================================
   ASK ARCHLENS
========================================= */

async function askArchLens() {

    const questionInput =
        document.getElementById(
            "question"
        );


    const answerSection =
        document.getElementById(
            "answerSection"
        );


    const answerContainer =
        document.getElementById(
            "answer"
        );


    const sourcesContainer =
        document.getElementById(
            "sources"
        );


    const button =
        document.getElementById(
            "askButton"
        );


    const question =
        questionInput.value.trim();


    if (!question) {

        alert(
            "Please enter a question."
        );

        return;
    }


    button.disabled = true;

    button.textContent =
        "Thinking...";


    answerSection.classList.remove(
        "hidden"
    );


    answerContainer.textContent =
        "Analyzing repository...";


    sourcesContainer.innerHTML = "";


    try {

        const response =
            await fetch(
                `${API_BASE_URL}/ask`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        question: question
                    })
                }
            );


        if (!response.ok) {

            throw new Error(
                `HTTP ${response.status}`
            );
        }


        const data =
            await response.json();


        answerContainer.textContent =
            data.answer ||
            "No answer returned.";


        const sources =
            data.sources || [];


        if (sources.length === 0) {

            sourcesContainer.innerHTML =
                `<span class="empty">
                    No sources available.
                </span>`;

        } else {

            sources.forEach(
                source => {

                    const span =
                        document.createElement(
                            "span"
                        );


                    span.className =
                        "source";


                    span.textContent =
                        source;


                    sourcesContainer.appendChild(
                        span
                    );

                }
            );
        }


    } catch (error) {

        console.error(error);


        answerContainer.textContent =
            "Could not connect to ArchLens backend.";
    }


    button.disabled = false;

    button.textContent =
        "Ask ArchLens";
}


/* =========================================
   HTML ESCAPE
========================================= */

function escapeHtml(value) {

    const div =
        document.createElement(
            "div"
        );


    div.textContent =
        String(value);


    return div.innerHTML;
}


/* =========================================
   EVENT LISTENERS
========================================= */

document
    .getElementById(
        "askButton"
    )
    .addEventListener(
        "click",
        askArchLens
    );


document
    .getElementById(
        "refreshArchitecture"
    )
    .addEventListener(
        "click",
        loadArchitecture
    );


/* =========================================
   INITIAL LOAD
========================================= */

loadArchitecture();
checkBackend();
