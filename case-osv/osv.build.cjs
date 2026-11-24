const fs = require("fs");
const path = require("path");
const SKILL = process.env.SKILLS_DIR ? path.join(process.env.SKILLS_DIR, "xlsx") : null;
if (!SKILL) {
  console.error("SKILLS_DIR is not set; expected <dir>/xlsx with helpers/ and vendor/");
  process.exit(3);
}
const ExcelJS = require(path.join(SKILL, "vendor", "exceljs.bundle.cjs"));
const H = require(path.join(SKILL, "helpers", "index.cjs"));

const ROWS = (() => {
  const raw = fs.readFileSync("data/osv.csv", "utf8").replace(/^\uFEFF/, "");
  const lines = raw.split(/\r?\n/).filter((l) => l.trim() !== "");
  const head = lines[0].split(",");
  return lines.slice(1).map((line) => {
    const cells = line.split(",");
    const row = {};
    head.forEach((k, i) => (row[k] = cells[i]));
    ["open_debit", "open_credit", "turn_debit", "turn_credit", "close_debit", "close_credit"].forEach(
      (k) => (row[k] = Number(row[k]) || 0)
    );
    return row;
  });
})();

const sum = (key) => ROWS.reduce((a, r) => a + r[key], 0);
const totals = {
  open_debit: sum("open_debit"), open_credit: sum("open_credit"),
  turn_debit: sum("turn_debit"), turn_credit: sum("turn_credit"),
  close_debit: sum("close_debit"), close_credit: sum("close_credit"),
};

const diffOf = (r) =>
  Math.round(((r.close_debit - r.close_credit) - ((r.open_debit - r.open_credit) + (r.turn_debit - r.turn_credit))) * 100) / 100;
const statusOf = (d) => (Math.abs(d) > 0.01 ? "ошибка" : "норма");

const rowsCalc = ROWS.map((r) => ({ ...r, diff: diffOf(r), status: statusOf(diffOf(r)) }));
const mismatchCount = rowsCalc.filter((r) => Math.abs(r.diff) > 0.01).length;
const redActive = ROWS.filter((r) => r.type === "активный").reduce((a, r) => a + r.close_credit, 0);
const redPassive = ROWS.filter((r) => r.type === "пассивный").reduce((a, r) => a + r.close_debit, 0);
const negCount = ROWS.reduce((a, r) => a + (r.turn_debit < 0 ? 1 : 0) + (r.turn_credit < 0 ? 1 : 0), 0);

const checks = [
  { name: "Сальдо на начало: Дт − Кт, ₽", formula: `SUM(${H.ref("ОСВ", "$D$5:$D$20")})-SUM(${H.ref("ОСВ", "$E$5:$E$20")})`, value: Math.round((totals.open_debit - totals.open_credit) * 100) / 100, expect: 0, tol: 0.01, fmt: H.FMT.rub },
  { name: "Обороты: Дт − Кт, ₽", formula: `SUM(${H.ref("ОСВ", "$F$5:$F$20")})-SUM(${H.ref("ОСВ", "$G$5:$G$20")})`, value: Math.round((totals.turn_debit - totals.turn_credit) * 100) / 100, expect: 0, tol: 0.01, fmt: H.FMT.rub },
  { name: "Сальдо на конец: Дт − Кт, ₽", formula: `SUM(${H.ref("ОСВ", "$H$5:$H$20")})-SUM(${H.ref("ОСВ", "$I$5:$I$20")})`, value: Math.round((totals.close_debit - totals.close_credit) * 100) / 100, expect: 0, tol: 0.01, fmt: H.FMT.rub },
  { name: "Строк с арифметическим расхождением, шт", formula: `SUMPRODUCT(--(ABS(${H.ref("ОСВ", "$J$5:$J$20")})>0.01))`, value: mismatchCount, expect: 0, tol: 0, fmt: H.FMT.int },
  { name: "Кредитовое сальдо на активных счетах, ₽", formula: `SUMPRODUCT((${H.ref("ОСВ", "$C$5:$C$20")}="активный")*${H.ref("ОСВ", "$I$5:$I$20")})`, value: redActive, expect: 0, tol: 0, fmt: H.FMT.rub },
  { name: "Дебетовое сальдо на пассивных счетах, ₽", formula: `SUMPRODUCT((${H.ref("ОСВ", "$C$5:$C$20")}="пассивный")*${H.ref("ОСВ", "$H$5:$H$20")})`, value: redPassive, expect: 0, tol: 0, fmt: H.FMT.rub },
  { name: "Отрицательных оборотов, шт", formula: `COUNTIF(${H.ref("ОСВ", "$F$5:$F$20")},"<0")+COUNTIF(${H.ref("ОСВ", "$G$5:$G$20")},"<0")`, value: negCount, expect: 0, tol: 0, fmt: H.FMT.int },
].map((c) => ({ ...c, status: Math.abs(c.value - c.expect) <= c.tol ? "норма" : "ошибка" }));

const problems = checks.filter((c) => c.status === "ошибка").length;

(async () => {
  const wb = new ExcelJS.Workbook();
  const dash = H.addSheet(wb, "Сводка");
  const osv = H.addSheet(wb, "ОСВ");
  const chk = H.addSheet(wb, "Проверки");

  // ---------- Сводка ----------
  H.widths(dash, [["A", 24], ["B", 18], ["C", 22], ["D", 18], ["E", 22], ["F", 18]]);
  H.titleBand(dash, "A1:F1", "ОСВ: проверка сходимости и красного сальдо",
    "Данные синтетические: ООО «Северный склад» вымышлен. Все числа считаются формулами от листа «ОСВ».");
  H.kpi(dash, "A3", "Счетов в ведомости", { formula: `COUNTA(${H.ref("ОСВ", "$A$5:$A$20")})`, result: ROWS.length }, H.FMT.int);
  H.kpi(dash, "C3", "Оборот по дебету, ₽", { formula: `SUM(${H.ref("ОСВ", "$F$5:$F$20")})`, result: totals.turn_debit }, H.FMT.rub);
  H.kpi(dash, "E3", "Оборот по кредиту, ₽", { formula: `SUM(${H.ref("ОСВ", "$G$5:$G$20")})`, result: totals.turn_credit }, H.FMT.rub);
  H.kpi(dash, "A5", "Расхождение оборотов, ₽", { formula: `ABS(${H.ref("ОСВ", "$F$21")}-${H.ref("ОСВ", "$G$21")})`, result: Math.abs(totals.turn_debit - totals.turn_credit) }, H.FMT.rub);
  H.kpi(dash, "C5", "Расхождение сальдо на конец, ₽", { formula: `ABS(${H.ref("ОСВ", "$H$21")}-${H.ref("ОСВ", "$I$21")})`, result: Math.abs(totals.close_debit - totals.close_credit) }, H.FMT.rub);
  H.kpi(dash, "E5", "Проверок с ошибкой, шт", { formula: `COUNTIF(${H.ref("Проверки", "$F$5:$F$11")},"ошибка")`, result: problems }, H.FMT.int);
  dash.getCell("A8").value = "Порядок: лист «ОСВ» — исходная ведомость с колонкой проверки по каждой строке; лист «Проверки» — семь утверждений с фактом, ожиданием и допуском.";
  dash.getCell("A8").font = { name: "Calibri", size: 10, color: { argb: "FF5B7186" } };
  dash.getCell("A8").alignment = { wrapText: true };
  dash.mergeCells("A8:F9");

  // ---------- ОСВ ----------
  H.widths(osv, [["A", 9], ["B", 46], ["C", 20], ["D", 14], ["E", 14], ["F", 14], ["G", 14], ["H", 14], ["I", 14], ["J", 13], ["K", 11]]);
  H.titleBand(osv, "A1:K1", "Оборотно-сальдовая ведомость за IV квартал",
    "Колонка «Проверка» = сальдо кон. − (сальдо нач. + оборот). Не ноль — расхождение.");
  const head = ["Счёт", "Наименование", "Тип счёта", "Сальдо нач. Дт", "Сальдо нач. Кт",
    "Обороты Дт", "Обороты Кт", "Сальдо кон. Дт", "Сальдо кон. Кт", "Проверка, ₽", "Статус"];
  head.forEach((t, i) => (osv.getCell(`${String.fromCharCode(65 + i)}4`).value = t));
  H.headerRow(osv, "A4:K4");

  rowsCalc.forEach((r, i) => {
    const row = 5 + i;
    osv.getCell(`A${row}`).value = r.account;
    osv.getCell(`A${row}`).numFmt = H.FMT.text;
    osv.getCell(`B${row}`).value = r.name;
    osv.getCell(`C${row}`).value = r.type;
    [["D", r.open_debit], ["E", r.open_credit], ["F", r.turn_debit], ["G", r.turn_credit],
      ["H", r.close_debit], ["I", r.close_credit]].forEach(([col, v]) => {
      osv.getCell(`${col}${row}`).value = v;
      osv.getCell(`${col}${row}`).numFmt = H.FMT.rub;
      osv.getCell(`${col}${row}`).alignment = { horizontal: "right" };
    });
    osv.getCell(`J${row}`).value = { formula: `(H${row}-I${row})-((D${row}-E${row})+(F${row}-G${row}))`, result: r.diff };
    osv.getCell(`J${row}`).numFmt = H.FMT.rub;
    osv.getCell(`K${row}`).value = { formula: `IF(ABS(J${row})>0.01,"ошибка","норма")`, result: r.status };
    osv.getCell(`K${row}`).alignment = { horizontal: "center" };
  });

  const totalRow = 5 + ROWS.length;
  osv.getCell(`A${totalRow}`).value = "Итого";
  ["D", "E", "F", "G", "H", "I"].forEach((col, idx) => {
    const key = ["open_debit", "open_credit", "turn_debit", "turn_credit", "close_debit", "close_credit"][idx];
    osv.getCell(`${col}${totalRow}`).value = { formula: `SUM(${col}5:${col}${totalRow - 1})`, result: totals[key] };
    osv.getCell(`${col}${totalRow}`).numFmt = H.FMT.rub;
    osv.getCell(`${col}${totalRow}`).alignment = { horizontal: "right" };
  });
  const totalDiff = Math.round(((totals.close_debit - totals.close_credit) - ((totals.open_debit - totals.open_credit) + (totals.turn_debit - totals.turn_credit))) * 100) / 100;
  osv.getCell(`J${totalRow}`).value = { formula: `(H${totalRow}-I${totalRow})-((D${totalRow}-E${totalRow})+(F${totalRow}-G${totalRow}))`, result: totalDiff };
  osv.getCell(`J${totalRow}`).numFmt = H.FMT.rub;
  osv.getCell(`K${totalRow}`).value = { formula: `IF(ABS(J${totalRow})>0.01,"ошибка","норма")`, result: statusOf(totalDiff) };

  H.body(osv, `A5:K${totalRow}`);
  H.body(osv, `A${totalRow}:K${totalRow}`);
  for (let c = 1; c <= 11; c++) {
    const cell = osv.getCell(`${String.fromCharCode(64 + c)}${totalRow}`);
    cell.font = { name: "Calibri", size: 10, bold: true, color: { argb: "FF12232E" } };
    cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FFD8E1EA" } };
  }
  H.cfEquals(osv, `K5:K${totalRow}`, "$K5", "ошибка", "FFF4C7C3", "FF7A1F17");

  // ---------- Проверки ----------
  H.widths(chk, [["A", 52], ["B", 16], ["C", 14], ["D", 16], ["E", 10], ["F", 12]]);
  H.titleBand(chk, "A1:F1", "Семь проверок ведомости",
    "Каждая строка — утверждение. «Факт» считается формулой, «Статус» сравнивает факт с ожиданием и допуском.");
  ["Показатель", "Факт", "Ожидание", "Разница", "Допуск", "Статус"].forEach(
    (t, i) => (chk.getCell(`${String.fromCharCode(65 + i)}4`).value = t));
  H.headerRow(chk, "A4:F4");

  checks.forEach((c, i) => {
    const row = 5 + i;
    chk.getCell(`A${row}`).value = c.name;
    chk.getCell(`B${row}`).value = { formula: c.formula, result: c.value };
    chk.getCell(`C${row}`).value = c.expect;
    chk.getCell(`D${row}`).value = { formula: `B${row}-C${row}`, result: Math.round((c.value - c.expect) * 100) / 100 };
    chk.getCell(`E${row}`).value = c.tol;
    chk.getCell(`F${row}`).value = { formula: `IF(ABS(B${row}-C${row})<=E${row},"норма","ошибка")`, result: c.status };
    [["B", c.fmt], ["C", c.fmt], ["D", c.fmt], ["E", H.FMT.rub]].forEach(([col, fmt]) => {
      chk.getCell(`${col}${row}`).numFmt = fmt;
      chk.getCell(`${col}${row}`).alignment = { horizontal: "right" };
    });
    chk.getCell(`F${row}`).alignment = { horizontal: "center" };
  });

  H.body(chk, "A5:F11");
  H.cfEquals(chk, "F5:F11", "$F5", "ошибка", "FFF4C7C3", "FF7A1F17");
  H.cfEquals(chk, "F5:F11", "$F5", "норма", "FFD7EFE1", "FF0F7B3F");

  H.freeze(osv, 4);
  H.freeze(chk, 4);

  await wb.xlsx.writeFile("osv.xlsx");
  console.log(`wrote osv.xlsx: ${ROWS.length} счетов, проверок ${checks.length}, проблем ${problems}`);
})();
