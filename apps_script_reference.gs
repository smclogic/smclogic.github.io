// ================================================================
// NEPSE COMPLETE SCRAPER — WIDE FORMAT  (with Turnover & Vol)
// ================================================================

function updateNepseComplete() {

  // ════════════════════════════════════════
  // PART 1: INDICES + SUB-INDICES
  // ════════════════════════════════════════
  var marketUrl = 'https://www.sharesansar.com/market';
  var marketRes = UrlFetchApp.fetch(marketUrl, {
    method: 'get', muteHttpExceptions: true,
    headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36' }
  });
  if (marketRes.getResponseCode() !== 200)
    throw new Error('Market page failed. HTTP: ' + marketRes.getResponseCode());

  var marketHtml = marketRes.getContentText();
  var dateStr    = extractDateFromHtml(marketHtml);
  var newDate    = normalizeDate(dateStr);

  var indicesRows    = getIndicesRows(marketHtml);
  var subIndicesRows = getSubIndicesRows(marketHtml);

  // Site index table columns: [0]=Name [1]=Open [2]=High [3]=Low [4]=Close [5]=PointChange [6]=%Change [7]=Turnover
  var indexMetrics   = ['Open', 'High', 'Low', 'Close', 'Turnover'];
  var displayNameMap = { 'NEPSE Index': 'Index' };
  var entityMap      = {};

  function addToEntityMap(row) {
    if (row.length < 8) return;
    var name = displayNameMap[row[0]] || row[0];
    if (!entityMap[name]) entityMap[name] = {};
    entityMap[name]['Open']     = row[1];
    entityMap[name]['High']     = row[2];
    entityMap[name]['Low']      = row[3];
    entityMap[name]['Close']    = row[4];
    // row[5] = Point Change — skipped
    // row[6] = % Change    — skipped
    // Store raw Turnover value, strip commas only
    entityMap[name]['Turnover'] = String(row[7] || '').replace(/,/g, '').trim();
  }
  indicesRows.forEach(addToEntityMap);
  subIndicesRows.forEach(addToEntityMap);

  if (!Object.keys(entityMap).length)
    throw new Error('No index/sub-index data found.');

  // ════════════════════════════════════════
  // PART 2: SYMBOL OHLC + Vol
  // ════════════════════════════════════════
  var priceUrl = 'https://www.sharesansar.com/today-share-price';
  var priceRes = UrlFetchApp.fetch(priceUrl, {
    method: 'get', muteHttpExceptions: true,
    headers: { 'User-Agent': 'Mozilla/5.0' }
  });

  var priceHtml  = priceRes.getContentText();
  var tableMatch = priceHtml.match(/<table[^>]*>([\s\S]*?)<\/table>/i);
  if (!tableMatch) throw new Error('Symbol table not found.');

  var rowRegex = /<tr[^>]*>([\s\S]*?)<\/tr>/gi;
  var allRows  = [];
  var rm;
  while ((rm = rowRegex.exec(tableMatch[0])) !== null) {
    var cells = [], cm;
    var cellRegex = /<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi;
    while ((cm = cellRegex.exec(rm[1])) !== null)
      cells.push(cm[1].replace(/<[^>]*>/g, '').replace(/&nbsp;/g, '').trim());
    if (cells.length) allRows.push(cells);
  }
  if (allRows.length < 2) throw new Error('No symbol rows found.');

  var hdr    = allRows[0].map(function(h) { return h.toLowerCase().trim(); });
  var colIdx = {
    symbol : hdr.findIndex(function(h) { return h === 'symbol'; }),
    open   : hdr.findIndex(function(h) { return h === 'open';   }),
    high   : hdr.findIndex(function(h) { return h === 'high';   }),
    low    : hdr.findIndex(function(h) { return h === 'low';    }),
    close  : hdr.findIndex(function(h) { return h === 'close';  }),
    volume : hdr.findIndex(function(h) { return h === 'vol'; })
  };

  var missing = ['symbol','open','high','low','close'].filter(function(k) { return colIdx[k] === -1; });
  if (missing.length) throw new Error('Symbol columns not found: ' + missing.join(', '));
  if (colIdx.volume === -1) Logger.log('Warning: "vol" column not found in symbol table. Headers found: ' + hdr.join(' | '));

  var symbolMap   = {};
  var symbolOrder = [];
  for (var r = 1; r < allRows.length; r++) {
    var sym = allRows[r][colIdx.symbol];
    if (!sym) continue;
    symbolMap[sym] = {
      open   : allRows[r][colIdx.open]   || '',
      high   : allRows[r][colIdx.high]   || '',
      low    : allRows[r][colIdx.low]    || '',
      close  : allRows[r][colIdx.close]  || '',
      volume : colIdx.volume !== -1 ? (allRows[r][colIdx.volume] || '') : ''
    };
    symbolOrder.push(sym);
  }
  if (!symbolOrder.length) throw new Error('No symbols parsed.');

  // ════════════════════════════════════════
  // PART 3: WRITE TO SHEET
  // ════════════════════════════════════════
  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('NepseComplete') || ss.insertSheet('NepseComplete');

  if (sheet.getLastRow() === 0) sheet.getRange(1, 1).setValue('Date');

  var lastColInit = sheet.getLastColumn() || 1;
  var headersInit = sheet.getRange(1, 1, 1, lastColInit).getValues()[0];
  var headerMap   = {};
  headersInit.forEach(function(h, i) { if (h) headerMap[h] = i + 1; });

  function ensureCol(title) {
    if (!headerMap[title]) {
      var col = (sheet.getLastColumn() || 0) + 1;
      sheet.getRange(1, col).setValue(title);
      headerMap[title] = col;
    }
    return headerMap[title];
  }

  // indexMetrics drives column creation (Open/High/Low/Close/Turnover)
  Object.keys(entityMap).forEach(function(name) {
    indexMetrics.forEach(function(metric) {
      if (entityMap[name].hasOwnProperty(metric))
        ensureCol(name + ' - ' + metric);
    });
  });

  // Symbol fields include Volume
  symbolOrder.forEach(function(sym) {
    ['Open', 'High', 'Low', 'Close', 'Volume'].forEach(function(f) {
      ensureCol(sym + '-' + f);
    });
  });

  // ── Stale / duplicate / holiday check ────────────────────────
  var lastRow = sheet.getLastRow();
  if (lastRow >= 2) {
    var lastDateVal  = sheet.getRange(lastRow, 1).getValue();
    var lastDateNorm = normalizeDate(lastDateVal);

    if (lastDateNorm && newDate) {
      if (newDate.getTime() === lastDateNorm.getTime()) {
        Logger.log('Row for ' + dateStr + ' already exists. Skipping.');
        return;
      }
      if (newDate.getTime() < lastDateNorm.getTime()) {
        Logger.log('Fetched date is older than last stored. Skipping.');
        return;
      }
    }

    var totalColsCheck = sheet.getLastColumn();
    var headersCheck   = sheet.getRange(1, 1, 1, totalColsCheck).getValues()[0];
    var prevRow        = sheet.getRange(lastRow, 1, 1, totalColsCheck).getValues()[0];
    var testRow        = buildOutputRow(dateStr, headersCheck, entityMap, symbolMap);
    var identical      = true;
    for (var j = 1; j < totalColsCheck; j++) {
      if (String(prevRow[j] || '') !== String(testRow[j] || '')) {
        identical = false;
        break;
      }
    }
    if (identical) {
      Logger.log('Scraped data matches last row. Website not updated yet. Skipping.');
      return;
    }
  }

  // ── Write new row ─────────────────────────────────────────────
  var totalCols = sheet.getLastColumn();
  var headers   = sheet.getRange(1, 1, 1, totalCols).getValues()[0];
  var outputRow = buildOutputRow(dateStr, headers, entityMap, symbolMap);
  sheet.getRange(sheet.getLastRow() + 1, 1, 1, totalCols).setValues([outputRow]);

  sheet.getRange(1, 1, 1, totalCols)
    .setBackground('#1F4E78').setFontColor('#FFFFFF').setFontWeight('bold');
  sheet.setFrozenRows(1);

  try { CacheService.getScriptCache().remove('nepse_fast_v1'); } catch(_) {}

  Logger.log('NepseComplete updated for ' + dateStr +
             ' | Indices: ' + Object.keys(entityMap).length +
             ' | Symbols: ' + symbolOrder.length);
}


// ── Build one output row aligned to current headers ───────────────
function buildOutputRow(dateStr, headers, entityMap, symbolMap) {
  var row = new Array(headers.length).fill('');
  row[0]  = dateStr;

  for (var c = 1; c < headers.length; c++) {
    var h = headers[c];
    if (!h) continue;

    // Covers Open|High|Low|Close|Turnover for indices/sub-indices
    var idxParts = h.match(/^(.+) - (Open|High|Low|Close|Turnover)$/i);
    if (idxParts) {
      var entity = idxParts[1], metric = idxParts[2];
      var key = metric.charAt(0).toUpperCase() + metric.slice(1).toLowerCase();
      if (key === 'Turnover') key = 'Turnover';
      if (entityMap[entity] && entityMap[entity][key] !== undefined)
        row[c] = entityMap[entity][key];
      continue;
    }

    // Covers Open|High|Low|Close|Volume for symbols
    var symParts = h.match(/^(.+)-(Open|High|Low|Close|Volume)$/i);
    if (symParts) {
      var sym   = symParts[1];
      var field = symParts[2].toLowerCase();
      if (symbolMap[sym]) row[c] = symbolMap[sym][field] || '';
    }
  }
  return row;
}


// ── PARSING HELPERS ───────────────────────────────────────────────

function getIndicesRows(html) {
  var tableRegex = /<table[^>]*>[\s\S]*?<thead[\s\S]*?<\/thead>[\s\S]*?<\/table>/i;
  var tableMatch = html.match(tableRegex);
  if (!tableMatch) return [];
  var tableHtml  = tableMatch[0].replace(/\r?\n|\r/g, ' ');
  var tbodyMatch = tableHtml.match(/<tbody[^>]*>([\s\S]*?)<\/tbody>/i);
  if (!tbodyMatch) return [];
  var trRegex = /<tr[^>]*>([\s\S]*?)<\/tr>/gi;
  var rows = [], m;
  while ((m = trRegex.exec(tbodyMatch[1])) !== null) {
    var cells = extractCells(m[1]);
    if (cells.length) rows.push(cells);
  }
  return rows;
}

function getSubIndicesRows(html) {
  var tables      = html.match(/<table[^>]*>[\s\S]*?<\/table>/gi) || [];
  var targetTable = null;
  for (var i = 0; i < tables.length; i++) {
    if (/Sub\s*Index/i.test(tables[i])) { targetTable = tables[i]; break; }
  }
  if (!targetTable) return [];
  var trRegex  = /<tr[^>]*>([\s\S]*?)<\/tr>/gi;
  var rows = [], m, isHeader = true;
  while ((m = trRegex.exec(targetTable)) !== null) {
    if (isHeader) { isHeader = false; continue; }
    var cells = extractCells(m[1]);
    if (cells.length) rows.push(cells);
  }
  return rows;
}

function extractDateFromHtml(html) {
  var m = html.match(/As\s+of[^0-9]*([0-9]{4}-[0-9]{2}-[0-9]{2})/i);
  return m ? m[1] : Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd');
}

function extractCells(rowHtml) {
  var cells = [], m;
  var cellRegex = /<t[dh][^>]*>([\s\S]*?)<\/t[dh]>/gi;
  while ((m = cellRegex.exec(rowHtml)) !== null) cells.push(cleanCell(m[1]));
  return cells;
}

function cleanCell(html) {
  return html
    .replace(/<[^>]*>/g, '')
    .replace(/&nbsp;/gi, ' ').replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<').replace(/&gt;/gi, '>')
    .replace(/&#(\d+);/g, function(_, c) { return String.fromCharCode(parseInt(c, 10)); })
    .trim();
}

function normalizeDate(value) {
  if (!value) return null;
  if (value instanceof Date)
    return new Date(value.getFullYear(), value.getMonth(), value.getDate());
  var d = new Date(value.toString());
  if (isNaN(d)) return null;
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}


// ── SCHEDULER ────────────────────────────────────────────────────

function runDaily() {
  var day = new Date().getDay();
  if (day === 0 || day === 6) { Logger.log('Weekend. Skipping.'); return; }
  updateNepseComplete();
}

function createDailyTrigger() {
  ScriptApp.getProjectTriggers().forEach(function(t) {
    if (t.getHandlerFunction() === 'runDaily') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('runDaily').timeBased().everyDays(1).atHour(18).create();
  Logger.log('Daily trigger created — runs at 12 UTC (≈ 5:45 PM NPT) Mon–Fri.');
}


// ── CUSTOM MENU ───────────────────────────────────────────────────

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('📈 NEPSE')
    .addItem('Update Now (Index + Symbols)', 'updateNepseComplete')
    .addItem('Setup Daily 6PM Trigger',      'createDailyTrigger')
    .addItem('Setup Keep-Warm Trigger',      'createKeepWarmTrigger')
    .addItem('Remove Keep-Warm Trigger',     'removeKeepWarmTrigger')
    .addToUi();
}


// ================================================================
//  WEB APP ENDPOINTS
// ================================================================

function doGet(e) {
  var type = e && e.parameter && e.parameter.type;
  if (type === 'caps') return getCapData();
  if (type === 'fast') return getFastData();
  return getNepseData();
}

function getFastData() {
  var cache  = CacheService.getScriptCache();
  var cached = cache.get('nepse_fast_v1');
  if (cached) {
    return ContentService.createTextOutput(cached).setMimeType(ContentService.MimeType.JSON);
  }

  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('NepseComplete');
  if (!sheet) {
    return ContentService
      .createTextOutput(JSON.stringify({ error: 'NepseComplete sheet not found.' }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  var lastRow = sheet.getLastRow();
  var lastCol = sheet.getLastColumn();
  if (lastRow < 2) {
    return ContentService.createTextOutput(JSON.stringify([])).setMimeType(ContentService.MimeType.JSON);
  }

  var headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  var keepIdx = [];
  for (var i = 0; i < headers.length; i++) {
    var h = String(headers[i] || '').trim();
    if (!h) continue;
    if (i === 0) { keepIdx.push(i); continue; }
    // Fast endpoint keeps Open|High|Low|Close|Turnover for indices/sub-indices
    if (/^.+ - (Open|High|Low|Close|Turnover)$/i.test(h)) keepIdx.push(i);
  }

  var keepHeaders = keepIdx.map(function(i) { return headers[i]; });
  var dataRows    = sheet.getRange(2, 1, lastRow - 1, lastCol).getValues();

  var result = dataRows.map(function(row) {
    var obj = {};
    for (var j = 0; j < keepIdx.length; j++) {
      var h = keepHeaders[j];
      var v = row[keepIdx[j]];
      if (v instanceof Date) {
        var yyyy = v.getFullYear();
        var mm   = String(v.getMonth() + 1).padStart(2, '0');
        var dd   = String(v.getDate()).padStart(2, '0');
        v = yyyy + '-' + mm + '-' + dd;
      }
      obj[h] = v;
    }
    return obj;
  });

  var json = JSON.stringify(result);
  try { cache.put('nepse_fast_v1', json, 300); } catch(_) {}
  return ContentService.createTextOutput(json).setMimeType(ContentService.MimeType.JSON);
}

function getNepseData() {
  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('NepseComplete');
  if (!sheet) {
    return ContentService
      .createTextOutput(JSON.stringify({ error: 'NepseComplete sheet not found.' }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  var lastRow = sheet.getLastRow();
  var lastCol = sheet.getLastColumn();
  if (lastRow < 2) {
    return ContentService.createTextOutput(JSON.stringify([])).setMimeType(ContentService.MimeType.JSON);
  }

  var headers  = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  var dataRows = sheet.getRange(2, 1, lastRow - 1, lastCol).getValues();

  var result = dataRows.map(function(row) {
    var obj = {};
    for (var i = 0; i < headers.length; i++) {
      var h = headers[i];
      if (!h) continue;
      var v = row[i];
      if (v instanceof Date) {
        var yyyy = v.getFullYear();
        var mm   = String(v.getMonth() + 1).padStart(2, '0');
        var dd   = String(v.getDate()).padStart(2, '0');
        v = yyyy + '-' + mm + '-' + dd;
      }
      obj[h] = v;
    }
    return obj;
  });

  return ContentService.createTextOutput(JSON.stringify(result)).setMimeType(ContentService.MimeType.JSON);
}

function getCapData() {
  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName('stock_cap');
  if (!sheet) {
    return ContentService
      .createTextOutput(JSON.stringify({ error: 'stock_cap sheet not found.' }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  var lastRow = sheet.getLastRow();
  if (lastRow < 2) {
    return ContentService
      .createTextOutput(JSON.stringify({ smallCap: [], midCap: [], highCap: [] }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  var data   = sheet.getRange(2, 1, lastRow - 1, 3).getValues();
  var result = { smallCap: [], midCap: [], highCap: [] };
  for (var i = 0; i < data.length; i++) {
    var a = String(data[i][0] || '').trim();
    var b = String(data[i][1] || '').trim();
    var c = String(data[i][2] || '').trim();
    if (a) result.smallCap.push(a);
    if (b) result.midCap.push(b);
    if (c) result.highCap.push(c);
  }
  return ContentService.createTextOutput(JSON.stringify(result)).setMimeType(ContentService.MimeType.JSON);
}


// ── KEEP-WARM ─────────────────────────────────────────────────────

function keepWarm() {
  try {
    UrlFetchApp.fetch(ScriptApp.getService().getUrl() + '?type=fast',
                      { method: 'get', muteHttpExceptions: true });
  } catch(_) {}
}

function createKeepWarmTrigger() {
  ScriptApp.getProjectTriggers().forEach(function(t) {
    if (t.getHandlerFunction() === 'keepWarm') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('keepWarm').timeBased().everyMinutes(4).create();
  Logger.log('Keep-warm trigger created.');
}

function removeKeepWarmTrigger() {
  ScriptApp.getProjectTriggers().forEach(function(t) {
    if (t.getHandlerFunction() === 'keepWarm') ScriptApp.deleteTrigger(t);
  });
  Logger.log('Keep-warm trigger removed.');
}