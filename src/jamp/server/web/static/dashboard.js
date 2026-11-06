(() => {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const graphElement = byId("evidence-graph");
  const detailElement = byId("evidence-detail");
  const errorElement = byId("dashboard-error");
  let chart = null;

  async function getJson(path) {
    const response = await fetch(path, {
      method: "GET",
      credentials: "same-origin",
      headers: { Accept: "application/json" }
    });
    if (response.status === 401) {
      window.location.assign("/dashboard/login");
      throw new Error("Сессия завершена. Выполните вход повторно.");
    }
    if (!response.ok) {
      throw new Error("HTTP " + response.status + " при запросе " + path);
    }
    return response.json();
  }

  function setText(id, value) {
    const element = byId(id);
    if (element) element.textContent = value === null || value === undefined ? "—" : String(value);
  }

  function statusColor(status) {
    if (status === "CLEAN") return "#22c55e";
    if (status === "HALLUCINATION_CAUGHT" || status === "INTEGRITY_VIOLATED") return "#f43f5e";
    if (status === "SUSPICIOUS" || status === "INCONCLUSIVE") return "#f59e0b";
    return "#94a3b8";
  }

  function showNodeDetails(node) {
    detailElement.textContent = JSON.stringify(node, null, 2);
  }

  function renderGraph(graph) {
    if (!graph || !Array.isArray(graph.nodes) || !Array.isArray(graph.edges)) {
      throw new Error("API вернул граф с нарушенным контрактом nodes/edges.");
    }

    const nodes = graph.nodes;
    const verdict = nodes.find((node) => node.type === "verdict");
    const evidence = nodes.filter((node) => node.type === "evidence");
    if (!verdict) {
      throw new Error("В сохранённом графе отсутствует узел verdict.");
    }

    if (!window.echarts) {
      throw new Error("ECharts CDN недоступен.");
    }
    if (chart) chart.dispose();
    chart = window.echarts.init(graphElement);

    const width = graphElement.clientWidth;
    const height = graphElement.clientHeight;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.max(90, Math.min(width, height) * 0.34);
    const positions = new Map();
    positions.set(verdict.id, { x: centerX, y: centerY });

    evidence.forEach((node, index) => {
      const angle = (2 * Math.PI * index) / Math.max(evidence.length, 1) - Math.PI / 2;
      positions.set(node.id, {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle)
      });
    });

    const chartNodes = nodes.map((node) => {
      const isVerdict = node.type === "verdict";
      const position = positions.get(node.id) || { x: centerX, y: centerY };
      const label = isVerdict
        ? (node.status || "VERDICT") + (node.package ? "\n" + node.package : "")
        : (node.evidence_type || "evidence") + " #" + (Number(node.sequence_no || 0) + 1);
      return {
        id: node.id,
        name: label,
        x: position.x,
        y: position.y,
        symbolSize: isVerdict ? 82 : 58,
        category: isVerdict ? 0 : 1,
        itemStyle: {
          color: isVerdict ? statusColor(node.status) : "#d6a84f",
          borderColor: isVerdict ? "#fecdd3" : "#f8d477",
          borderWidth: 2
        },
        label: {
          show: true,
          color: "#e2e8f0",
          fontSize: isVerdict ? 12 : 11,
          position: isVerdict ? "bottom" : "inside",
          overflow: "break"
        },
        raw: node
      };
    });

    const nodeIds = new Set(nodes.map((node) => node.id));
    const links = graph.edges
      .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
      .map((edge) => ({
        source: edge.source,
        target: edge.target,
        value: edge.relation || "persisted relationship",
        lineStyle: { color: "#64748b", width: 2, opacity: 0.8 },
        label: { show: false }
      }));

    chart.setOption({
      animationDuration: 350,
      tooltip: {
        formatter: (params) => {
          if (params.dataType !== "node") return params.data.value || "";
          const raw = params.data.raw || {};
          return raw.type === "verdict"
            ? "Verdict: " + (raw.status || "UNKNOWN")
            : "Evidence: " + (raw.evidence_type || "UNKNOWN");
        }
      },
      series: [{
        type: "graph",
        layout: "none",
        data: chartNodes,
        links,
        roam: true,
        draggable: true,
        edgeSymbol: ["none", "arrow"],
        edgeSymbolSize: 8,
        lineStyle: { curveness: 0.08 },
        emphasis: { focus: "adjacency", lineStyle: { width: 3 } }
      }]
    });

    chart.off("click");
    chart.on("click", (params) => {
      if (params.dataType === "node" && params.data && params.data.raw) {
        showNodeDetails(params.data.raw);
      }
    });
    if (chartNodes.length > 0) showNodeDetails(verdict);
  }

  async function loadDashboard() {
    try {
      const stats = await getJson("/v1/stats");
      setText("total-checks", stats.total_checks);
      setText("hallucinations-caught", stats.hallucinations_caught);
      setText("inconclusive-count", stats.inconclusive);

      const latest = await getJson("/v1/verdicts?limit=1");
      const item = Array.isArray(latest.items) ? latest.items[0] : null;
      if (!item) {
        setText("verdict-summary", "Пока нет сохранённых проверок.");
        setText("verdict-status", "Нет данных");
        graphElement.textContent = "Нет сохранённых verdict rows.";
        return;
      }

      setText("verdict-summary", (item.package || "Пакет не указан") + " · " + item.status);
      setText("verdict-id", item.verdict_id);
      setText("verdict-status", item.status);
      setText("verdict-package", item.package);
      setText("verdict-code-hash", item.code_hash);

      const graph = await getJson(
        "/v1/verdicts/" + encodeURIComponent(item.verdict_id) + "/graph"
      );
      renderGraph(graph);
    } catch (error) {
      errorElement.textContent = error instanceof Error ? error.message : String(error);
      errorElement.classList.remove("hidden");
    }
  }

  window.addEventListener("resize", () => {
    if (chart) chart.resize();
  });
  loadDashboard();
})();
