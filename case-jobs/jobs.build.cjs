const fs = require("fs");
const path = require("path");
const SKILL = process.env.SKILLS_DIR ? path.join(process.env.SKILLS_DIR, "xlsx") : null;
if (!SKILL) {
  console.error("SKILLS_DIR is not set; expected <dir>/xlsx with helpers/ and vendor/");
  process.exit(3);
}
const ExcelJS = require(path.join(SKILL, "vendor", "exceljs.bundle.cjs"));
const H = require(path.join(SKILL, "helpers", "index.cjs"));

function parseCsv(text) {
  const rows = [];
  let row = [], cur = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"') {
        if (text[i + 1] === '"') { cur += '"'; i++; } else q = false;
      } else cur += c;
    } else if (c === '"') q = true;
    else if (c === ",") { row.push(cur); cur = ""; }
    else if (c === "\n") { row.push(cur); rows.push(row); row = []; cur = ""; }
    else if (c !== "\r") cur += c;
  }
  if (cur !== "" || row.length) { row.push(cur); rows.push(row); }
  const head = rows.shift().map((h) => h.replace(/^\uFEFF/, ""));
  return rows
    .filter((r) => r.length === head.length)
    .map((r) => Object.fromEntries(head.map((h, i) => [h, r[i]])));
}

const jobs = parseCsv(fs.readFileSync("data/jobs.csv", "utf8"));
const regions = parseCsv(fs.readFileSync("data/by_region.csv", "utf8"));
const specs = parseCsv(fs.readFileSync("data/by_specialisation.csv", "utf8"));
const summary = JSON.parse(fs.readFileSync("data/summary.json", "utf8"));
const num = (v) => Number(v) || 0;

(async () => {
  const wb = new ExcelJS.Workbook();
  const dash = H.addSheet(wb, "Сводка");
  const reg = H.addSheet(wb, "Регионы");
  const spec = H.addSheet(wb, "Специальности");
  const rules = H.addSheet(wb, "Правила сбора");
  const data = H.addSheet(wb, "Данные");

  // ---------- Сводка ----------
  H.widths(dash, [["A", 26], ["B", 18], ["C", 24], ["D", 18], ["E", 24], ["F", 18]]);
  H.titleBand(dash, "A1:F1", "Открытые данные о вакансиях: что можно анализировать без персональных данных",
    "Источник: opendata.trudvsem.ru. Собирается только белый список полей — контактов в таблице нет.");
  const regLast = 4 + regions.length;
  H.kpi(dash, "A3", "Вакансий в таблице", { formula: `COUNTA(${H.ref("Данные", "$A$5:$A$" + (4 + jobs.length))})`, result: jobs.length }, H.FMT.int);
  H.kpi(dash, "C3", "С указанной зарплатой", { formula: `SUM(${H.ref("Регионы", `$C$5:$C$${regLast}`)})`, result: summary.with_salary }, H.FMT.int);
  H.kpi(dash, "E3", "Медианная зарплата, ₽", summary.median_salary, H.FMT.rub);
  H.kpi(dash, "A5", "Регионов", { formula: `COUNTA(${H.ref("Регионы", `$A$5:$A$${regLast}`)})`, result: summary.regions }, H.FMT.int);
  H.kpi(dash, "C5", "Специальностей", { formula: `COUNTA(${H.ref("Специальности", `$A$5:$A$${4 + specs.length}`)})`, result: summary.specialisations }, H.FMT.int);
  H.kpi(dash, "E5", "Доля без зарплаты", Math.round((1 - summary.with_salary / summary.rows) * 1000) / 1000, H.FMT.pct1);
  dash.getCell("A8").value =
    "Правовая рамка: данные открыты и допускают использование без ограничений; при копировании нужна ссылка на trudvsem.ru. " +
    "Персональные данные в таблицу не попадают по устройству конвейера, а не по обещанию: колонки contact_person, contact_list, email и свободные тексты " +
    "требований не входят в белый список, а проверка ищет почты и телефоны регуляркой.";
  dash.getCell("A8").font = { name: "Calibri", size: 10, color: { argb: "FF5B7186" } };
  dash.getCell("A8").alignment = { wrapText: true, vertical: "top" };
  dash.mergeCells("A8:F11");
  dash.getCell("A13").value = `Период публикаций: ${summary.date_min} — ${summary.date_max}. Всего строк ${summary.rows}.`;
  dash.getCell("A13").font = { name: "Calibri", size: 10, color: { argb: "FF5B7186" } };

  // ---------- Регионы ----------
  H.widths(reg, [["A", 34], ["B", 12], ["C", 15], ["D", 15], ["E", 18]]);
  H.titleBand(reg, "A1:E1", "Разрез по регионам", "Сортировка по числу вакансий. Доля без зарплаты считается внутри региона.");
  ["Регион", "Вакансий", "С зарплатой", "Медиана, ₽", "Доля без зарплаты"].forEach(
    (t, i) => (reg.getCell(`${String.fromCharCode(65 + i)}4`).value = t));
  H.headerRow(reg, "A4:E4");
  regions.forEach((r, i) => {
    const row = 5 + i;
    reg.getCell(`A${row}`).value = r.name;
    reg.getCell(`B${row}`).value = num(r.count);
    reg.getCell(`B${row}`).numFmt = H.FMT.int;
    reg.getCell(`C${row}`).value = num(r.with_salary);
    reg.getCell(`C${row}`).numFmt = H.FMT.int;
    reg.getCell(`D${row}`).value = num(r.median);
    reg.getCell(`D${row}`).numFmt = H.FMT.rub;
    reg.getCell(`E${row}`).value = num(r.no_salary_share);
    reg.getCell(`E${row}`).numFmt = H.FMT.pct1;
    for (const col of ["B", "C", "D", "E"]) reg.getCell(`${col}${row}`).alignment = { horizontal: "right" };
  });
  H.body(reg, `A5:E${regLast}`);
  const regTotal = regLast + 1;
  reg.getCell(`A${regTotal}`).value = "Итого";
  reg.getCell(`B${regTotal}`).value = { formula: `SUM(B5:B${regLast})`, result: jobs.length };
  reg.getCell(`C${regTotal}`).value = { formula: `SUM(C5:C${regLast})`, result: summary.with_salary };
  for (const col of ["B", "C"]) {
    reg.getCell(`${col}${regTotal}`).numFmt = H.FMT.int;
    reg.getCell(`${col}${regTotal}`).alignment = { horizontal: "right" };
  }
  reg.getCell(`D${regTotal}`).value = summary.median_salary;
  reg.getCell(`D${regTotal}`).numFmt = H.FMT.rub;
  reg.getCell(`D${regTotal}`).alignment = { horizontal: "right" };
  for (let c = 1; c <= 5; c++) {
    const cell = reg.getCell(`${String.fromCharCode(64 + c)}${regTotal}`);
    cell.font = { name: "Calibri", size: 10, bold: true, color: { argb: "FF12232E" } };
    cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FFD8E1EA" } };
  }
  H.dataBar(reg, `B5:B${regLast}`, "FF9CC0F0");
  H.freeze(reg, 4);

  // ---------- Специальности ----------
  const specLast = 4 + specs.length;
  H.widths(spec, [["A", 40], ["B", 12], ["C", 15], ["D", 15], ["E", 18]]);
  H.titleBand(spec, "A1:E1", "Разрез по специальностям", "Категория из карточки вакансии, а не пересказ названия.");
  ["Специальность", "Вакансий", "С зарплатой", "Медиана, ₽", "Доля без зарплаты"].forEach(
    (t, i) => (spec.getCell(`${String.fromCharCode(65 + i)}4`).value = t));
  H.headerRow(spec, "A4:E4");
  specs.forEach((r, i) => {
    const row = 5 + i;
    spec.getCell(`A${row}`).value = r.name;
    spec.getCell(`B${row}`).value = num(r.count);
    spec.getCell(`B${row}`).numFmt = H.FMT.int;
    spec.getCell(`C${row}`).value = num(r.with_salary);
    spec.getCell(`C${row}`).numFmt = H.FMT.int;
    spec.getCell(`D${row}`).value = num(r.median);
    spec.getCell(`D${row}`).numFmt = H.FMT.rub;
    spec.getCell(`E${row}`).value = num(r.no_salary_share);
    spec.getCell(`E${row}`).numFmt = H.FMT.pct1;
    for (const col of ["B", "C", "D", "E"]) spec.getCell(`${col}${row}`).alignment = { horizontal: "right" };
  });
  H.body(spec, `A5:E${specLast}`);
  H.dataBar(spec, `B5:B${specLast}`, "FF9CC0F0");
  H.freeze(spec, 4);

  // ---------- Правила сбора ----------
  H.widths(rules, [["A", 30], ["B", 16], ["C", 78]]);
  H.titleBand(rules, "A1:C1", "Белый список полей", "Что попадает в таблицу и что не попадает — с причиной по каждому полю.");
  ["Поле", "Решение", "Причина"].forEach((t, i) => (rules.getCell(`${String.fromCharCode(65 + i)}4`).value = t));
  H.headerRow(rules, "A4:C4");
  const policy = [
    ["id", "берём", "Внутренний номер вакансии: нужен для дедупликации и сверки."],
    ["region, region_code", "берём", "География — основа разрезов."],
    ["company", "берём", "Название работодателя: юридическое лицо, не человек."],
    ["job", "берём", "Предмет поиска."],
    ["specialisation", "берём", "Категория из карточки — готовая группировка."],
    ["employment, schedule", "берём", "Условия работы: тип занятости и график."],
    ["experience", "берём", "Требуемый стаж в годах."],
    ["salary_min, salary_max, currency", "берём", "Деньги — то, что анализируется."],
    ["date, url", "берём", "Дата публикации и ссылка на первоисточник."],
    ["contact_person", "не берём", "Имя конкретного человека — персональные данные."],
    ["contact_list", "не берём", "Телефоны и адреса почты рекрутёров."],
    ["company.email", "не берём", "Корпоративная почта: это тоже контакт, хотя и не личный."],
    ["requirements, duty, term", "не берём", "Свободный текст: чаще всего телефоны и почты лежат именно там."],
    ["inn, kpp, ogrn", "не берём", "Для разрезов не нужны: меньше данных — меньше риска и шума."],
  ];
  policy.forEach((r, i) => {
    const row = 5 + i;
    rules.getCell(`A${row}`).value = r[0];
    rules.getCell(`B${row}`).value = r[1];
    rules.getCell(`B${row}`).alignment = { horizontal: "center" };
    rules.getCell(`C${row}`).value = r[2];
    rules.getCell(`C${row}`).alignment = { wrapText: true, vertical: "top" };
  });
  H.body(rules, `A5:C${4 + policy.length}`);
  H.cfEquals(rules, `B5:B${4 + policy.length}`, "$B5", "берём", "FFD7EFE1", "FF0F7B3F");
  H.cfEquals(rules, `B5:B${4 + policy.length}`, "$B5", "не берём", "FFF4C7C3", "FF7A1F17");
  H.freeze(rules, 4);

  // ---------- Данные ----------
  const COLS = [
    ["id", "id", 38], ["region", "Регион", 30], ["region_code", "Код ОКАТО", 14],
    ["company", "Работодатель", 40], ["job", "Должность", 46], ["specialisation", "Специальность", 30],
    ["employment", "Занятость", 18], ["schedule", "График", 20], ["experience", "Стаж, лет", 10],
    ["salary_min", "Зарплата от", 12], ["salary_max", "Зарплата до", 12], ["currency", "Валюта", 9],
    ["date", "Дата", 11], ["url", "Ссылка", 48],
  ];
  // Колонки берём только те, что есть в CSV: публичная копия выходит без работодателя.
  const present = new Set(Object.keys(jobs[0] || {}));
  const cols = COLS.filter(([k]) => present.has(k));
  const last = colLetter(cols.length - 1);
  H.widths(data, cols.map(([, , w], i) => [colLetter(i), w]));
  cols.forEach(([, title], i) => (data.getCell(`${colLetter(i)}4`).value = title));
  H.headerRow(data, `A4:${last}4`);
  const numCols = new Set(["salary_min", "salary_max", "experience"]);
  const wrapCols = new Set(["region", "company", "job", "specialisation", "employment", "schedule"]);
  jobs.forEach((r, i) => {
    const row = 5 + i;
    cols.forEach(([k], j) => {
      const cell = data.getCell(`${colLetter(j)}${row}`);
      if (numCols.has(k)) {
        cell.value = num(r[k]);
        cell.numFmt = H.FMT.int;
        cell.alignment = { horizontal: "right" };
        return;
      }
      cell.value = r[k];
      // id — идентификатор-строка: без текстового формата линтер принимает UUID за формулу.
      if (k === "id") cell.numFmt = H.FMT.text;
      if (wrapCols.has(k)) cell.alignment = { wrapText: true, vertical: "top" };
    });
  });
  H.body(data, `A5:${last}${4 + jobs.length}`);
  data.autoFilter = { from: "A4", to: `${last}4` };
  H.freeze(data, 4, 2);

  await wb.xlsx.writeFile("jobs.xlsx");
  console.log(`wrote jobs.xlsx: ${jobs.length} строк, ${regions.length} регионов, ${specs.length} специальностей`);
})();

function colLetter(i) {
  return String.fromCharCode(65 + i);
}
