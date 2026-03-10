// ThaiCarbide — Google Ads Conversion Tracking
// Google Ads ID: AW-18001691387
// Update the labels below when you get them from Google Ads

const AW_ID = 'AW-18001691387';

const LABELS = {
  LINE_CLICK:  'LINE_CLICK',   // replace with real label from Google Ads
  FORM_SUBMIT: 'FORM_SUBMIT',  // replace with real label from Google Ads
  PHONE_CLICK: 'PHONE_CLICK',  // replace with real label from Google Ads
};

function fireConversion(label, value) {
  if (typeof gtag === 'undefined') {
    console.warn('[ConvTracking] gtag not available — skipping:', label);
    return;
  }
  gtag('event', 'conversion', {
    send_to: AW_ID + '/' + label,
    value: value,
    currency: 'THB',
  });
}

// ── Event delegation on document — works for dynamic elements ──

document.addEventListener('click', function (e) {
  var target = e.target.closest('a');
  if (!target) return;

  var href = target.href || '';

  // 1. LINE click
  if (href.indexOf('line.me') !== -1 || href.indexOf('line://') !== -1) {
    console.log('[ConvTracking] LINE click — value: 10 THB | href:', href);
    fireConversion(LABELS.LINE_CLICK, 10);
    return;
  }

  // 3. Phone click
  if (href.indexOf('tel:') === 0) {
    console.log('[ConvTracking] Phone click — value: 5 THB | href:', href);
    fireConversion(LABELS.PHONE_CLICK, 5);
    return;
  }
});

// 2. Form submit (event delegation)
document.addEventListener('submit', function (e) {
  var form = e.target;
  console.log('[ConvTracking] Form submit — value: 8 THB | form:', form.id || form.action || '(unnamed)');
  fireConversion(LABELS.FORM_SUBMIT, 8);
});

console.log('[ConvTracking] Loaded on', window.location.pathname, '| ID:', AW_ID);
