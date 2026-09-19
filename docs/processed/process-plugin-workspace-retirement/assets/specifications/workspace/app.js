(() => {
  "use strict";

  const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches;

  try {
    if (
      window.parent !== window
      && window.parent.location.origin === window.location.origin
    ) {
      document.documentElement.dataset.agentFactoryWorkspaceEmbedded = "true";
    }
  } catch {
    // Standalone and cross-origin hosts retain the document's normal theme.
  }

  if (window.mermaid) {
    window.mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: prefersDark ? "dark" : "neutral",
      flowchart: {
        curve: "linear",
        htmlLabels: false,
        nodeSpacing: 28,
        rankSpacing: 38,
        useMaxWidth: true,
      },
      themeVariables: {
        fontFamily: '"Pretendard", "Noto Sans KR", "Noto Sans CJK KR", "Apple SD Gothic Neo", "Malgun Gothic", system-ui, sans-serif',
        fontSize: "14px",
      },
    });

    window.mermaid.run({ querySelector: ".mermaid" }).catch((error) => {
      console.error("Mermaid diagram rendering failed", error);
    });
  }

  if (window.Tabulator) {
    document.querySelectorAll(".table > table").forEach((table) => {
      const wrapper = table.parentElement;
      const headerCells = [...table.querySelectorAll("thead th")];
      const sourceRows = [...table.querySelectorAll("tbody tr")];
      const columnCount = Math.max(
        headerCells.length,
        ...sourceRows.map((row) => row.children.length),
      );
      const sortIcon = '<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true" focusable="false"><path d="m3 5 3-3 3 3M3 7l3 3 3-3" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"/></svg>';
      const columns = Array.from({ length: columnCount }, (_unused, index) => ({
        title: headerCells[index]?.innerHTML || "",
        field: `column${index}`,
        formatter: "html",
        headerSort: headerCells.length > 0,
      }));
      const data = sourceRows.map((row) =>
        Object.fromEntries(
          [...row.children].map((cell, index) => [`column${index}`, cell.innerHTML]),
        ),
      );
      try {
        const host = document.createElement("div");
        host.className = "tabulator-host";
        table.before(host);
        new window.Tabulator(host, {
          data,
          columns,
          headerVisible: headerCells.length > 0,
          headerSortElement: sortIcon,
          layout: "fitDataStretch",
          movableColumns: true,
          columnHeaderVertAlign: "middle",
          placeholder: "표시할 항목이 없습니다.",
        });
        table.hidden = true;
        wrapper?.classList.add("table-enhanced");
      } catch (error) {
        console.error("Tabulator table rendering failed", error);
      }
    });
  }
})();
