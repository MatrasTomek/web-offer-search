from html import escape
from pathlib import Path

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>Zlecenia web-dev — raport</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
  h1 {{ font-size: 1.4rem; }}
  .meta {{ color: #555; margin-bottom: 1rem; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ border: 1px solid #ddd; padding: 0.5rem; text-align: left; vertical-align: top; }}
  th {{ background: #f4f4f4; cursor: pointer; user-select: none; }}
  tr.new-lead {{ background: #fff8d8; }}
  .empty {{ color: #555; font-style: italic; }}
</style>
</head>
<body>
<h1>Zlecenia web-dev — raport</h1>
<p class="meta">Wygenerowano: {generated_at}<br>Źródła, które nie odpowiedziały: {failed}</p>
{empty_message}
<table id="leads">
<thead>
<tr>
  <th data-col="0">Źródło</th>
  <th data-col="1">Tytuł / Opis</th>
  <th data-col="2">Budżet / Wartość</th>
  <th data-col="3">Data publikacji</th>
  <th data-col="4">Link bezpośredni</th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
<script>
document.querySelectorAll('th[data-col]').forEach(function (th) {{
  th.addEventListener('click', function () {{
    var col = parseInt(th.dataset.col, 10);
    var tbody = document.querySelector('#leads tbody');
    var rows = Array.from(tbody.querySelectorAll('tr'));
    var asc = th.dataset.asc !== 'true';
    rows.sort(function (a, b) {{
      var av = a.children[col].textContent.trim().toLowerCase();
      var bv = b.children[col].textContent.trim().toLowerCase();
      return asc ? av.localeCompare(bv) : bv.localeCompare(av);
    }});
    th.dataset.asc = asc;
    rows.forEach(function (row) {{ tbody.appendChild(row); }});
  }});
}});
</script>
</body>
</html>
"""

_ROW_TEMPLATE = """<tr class="{row_class}">
  <td>{source}</td>
  <td><strong>{title}</strong><br>{description}</td>
  <td>{value}</td>
  <td>{published_at}</td>
  <td><a href="{link}" target="_blank" rel="noopener">otwórz</a></td>
</tr>"""


def _render_row(lead: dict) -> str:
    row_class = "new-lead" if lead.get("is_new") else ""
    value = lead.get("value") or "—"
    return _ROW_TEMPLATE.format(
        row_class=row_class,
        source=escape(lead["source"]),
        title=escape(lead["title"]),
        description=escape(lead["description"][:300]),
        value=escape(str(value)),
        published_at=escape(str(lead["published_at"])),
        link=escape(lead["link"]),
    )


def render_html(leads: list[dict], failed_sources: list[str], generated_at: str) -> str:
    rows = "\n".join(_render_row(lead) for lead in leads)
    failed = ", ".join(escape(s) for s in failed_sources) if failed_sources else "brak"
    empty_message = "" if leads else '<p class="empty">Brak zleceń spełniających kryteria w tym przebiegu.</p>'
    return _PAGE_TEMPLATE.format(
        generated_at=escape(generated_at),
        failed=failed,
        rows=rows,
        empty_message=empty_message,
    )


def write_report(leads: list[dict], failed_sources: list[str], generated_at: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(leads, failed_sources, generated_at), encoding="utf-8")
