(function () {
  const data = window.INVOICE_DATA;
  const productsById = Object.fromEntries(data.products.map(p => [String(p.id), p]));
  const customersById = Object.fromEntries(data.customers.map(c => [String(c.id), c]));
  const tbody = document.querySelector('#items tbody');
  const tpl = document.getElementById('row-template');
  const taxType = document.getElementById('tax_type');

  const round2 = n => Math.round((n + Number.EPSILON) * 100) / 100;
  const fmt = n => round2(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const num = el => parseFloat(el.value) || 0;

  function addRow(line) {
    const row = tpl.content.firstElementChild.cloneNode(true);
    const sel = row.querySelector('.product');
    data.products.forEach(p => {
      const o = document.createElement('option');
      o.value = p.id;
      o.textContent = (p.sku ? p.sku + ' · ' : '') + p.name;
      sel.appendChild(o);
    });
    if (line) {
      sel.value = line.product_id || '';
      row.querySelector('.description').value = line.description || '';
      row.querySelector('.hsn').value = line.hsn || '';
      row.querySelector('.unit').value = line.unit || '';
      row.querySelector('.qty').value = line.qty;
      row.querySelector('.price').value = line.price;
      row.querySelector('.disc').value = line.discount_pct || 0;
      row.querySelector('.gst').value = String(line.gst_rate);
    }
    sel.addEventListener('change', () => applyProduct(row));
    toggleCustomName(row);
    row.querySelector('.remove').addEventListener('click', () => {
      row.remove();
      if (!tbody.children.length) addRow();
      recalc();
    });
    row.addEventListener('input', recalc);
    row.addEventListener('change', recalc);
    tbody.appendChild(row);
    updateStockHint(row);
    return row;
  }

  // The item name box is only shown for custom (non-stock) items
  function toggleCustomName(row) {
    const custom = !row.querySelector('.product').value;
    const name = row.querySelector('.description');
    name.hidden = !custom;
  }

  function applyProduct(row) {
    const p = productsById[row.querySelector('.product').value];
    toggleCustomName(row);
    if (!p) row.querySelector('.description').value = '';
    if (p) {
      row.querySelector('.description').value = p.name;
      row.querySelector('.hsn').value = p.hsn || '';
      row.querySelector('.unit').value = p.unit || '';
      row.querySelector('.price').value = p.price;
      row.querySelector('.gst').value = String(p.gst_rate);
    }
    updateStockHint(row);
    recalc();
  }

  function updateStockHint(row) {
    const p = productsById[row.querySelector('.product').value];
    const hint = row.querySelector('.stock-hint');
    if (!p) { hint.textContent = ''; hint.className = 'stock-hint muted'; return; }
    const need = num(row.querySelector('.qty'));
    hint.textContent = 'In stock: ' + p.stock + ' ' + (p.unit || '');
    hint.className = 'stock-hint ' + (need > p.stock ? 'bad' : 'muted');
  }

  function recalc() {
    let subtotal = 0, discount = 0, tax = 0, taxableTotal = 0;
    tbody.querySelectorAll('tr').forEach(row => {
      const gross = round2(num(row.querySelector('.qty')) * num(row.querySelector('.price')));
      const disc = round2(gross * num(row.querySelector('.disc')) / 100);
      const taxable = round2(gross - disc);
      const t = round2(taxable * num(row.querySelector('.gst')) / 100);
      row.querySelector('.taxable').textContent = fmt(taxable);
      row.querySelector('.amount').textContent = fmt(taxable + t);
      subtotal += gross; discount += disc; tax += t; taxableTotal += taxable;
      updateStockHint(row);
    });
    const exact = round2(subtotal - discount + tax);
    const total = Math.round(exact);
    const inter = taxType.value === 'inter';
    document.querySelectorAll('.totals .intra').forEach(el => el.hidden = inter);
    document.querySelectorAll('.totals .inter').forEach(el => el.hidden = !inter);
    document.getElementById('t-subtotal').textContent = fmt(subtotal);
    document.getElementById('t-discount').textContent = (discount ? '-' : '') + fmt(discount);
    document.getElementById('t-taxable').textContent = fmt(taxableTotal);
    document.getElementById('t-cgst').textContent = fmt(tax / 2);
    document.getElementById('t-sgst').textContent = fmt(tax / 2);
    document.getElementById('t-igst').textContent = fmt(tax);
    document.getElementById('t-round').textContent = fmt(total - exact);
    document.getElementById('t-total').textContent = '₹' + fmt(total);
  }

  // Customer picker fills the bill-to fields
  const custSel = document.getElementById('customer-select');
  const saveWrap = document.getElementById('save-customer-wrap');
  custSel.addEventListener('change', () => {
    const c = customersById[custSel.value];
    ['name', 'phone', 'address', 'gstin'].forEach(k => {
      document.getElementById('customer_' + k).value = c ? (c[k] || '') : '';
    });
    saveWrap.hidden = !!c;
  });
  saveWrap.hidden = !!custSel.value;

  // Ship-to address mirrors the bill-to address while "same as" is ticked
  const billAddr = document.getElementById('customer_address');
  const shipAddr = document.getElementById('ship_to_address');
  const shipSame = document.getElementById('ship_same');
  function syncShipTo() {
    shipAddr.readOnly = shipSame.checked;
    if (shipSame.checked) shipAddr.value = billAddr.value;
  }
  shipSame.addEventListener('change', () => { syncShipTo(); if (!shipSame.checked) shipAddr.focus(); });
  billAddr.addEventListener('input', syncShipTo);
  custSel.addEventListener('change', syncShipTo);
  syncShipTo();

  taxType.addEventListener('change', recalc);
  document.getElementById('add-row').addEventListener('click', () => addRow().querySelector('.product').focus());

  if (data.lines.length) data.lines.forEach(addRow); else addRow();
  recalc();
})();
