// ThaiCarbide — Google Ads Conversion Tracking
// Replace AW-XXXXXXXXX and CONV_LABEL_HERE with real values from Google Ads

const AW_ID    = 'AW-XXXXXXXXX';
const AW_LABEL = 'CONV_LABEL_HERE';

function fireConversion(value, label) {
  if (typeof gtag === 'undefined') {
    console.warn('[ConvTracking] gtag not loaded — conversion not fired');
    return;
  }
  gtag('event', 'conversion', {
    send_to: AW_ID + '/' + (label || AW_LABEL),
    value: value,
    currency: 'THB',
  });
}

document.addEventListener('DOMContentLoaded', function () {

  // ── LINE clicks ──────────────────────────────────────────────
  document.querySelectorAll('a[href*="line.me"]').forEach(function (el) {
    el.addEventListener('click', function () {
      console.log('[ConvTracking] LINE click fired — value: 10 THB', el.href);
      fireConversion(10, AW_LABEL);
    });
  });

  // ── Phone (tel:) clicks ──────────────────────────────────────
  document.querySelectorAll('a[href^="tel:"]').forEach(function (el) {
    el.addEventListener('click', function () {
      console.log('[ConvTracking] Phone click fired — value: 5 THB', el.href);
      fireConversion(5, AW_LABEL);
    });
  });

  // ── Form submissions ─────────────────────────────────────────
  document.querySelectorAll('form').forEach(function (form) {
    form.addEventListener('submit', function () {
      console.log('[ConvTracking] Form submit fired — value: 8 THB', form.id || form.action || '(unnamed form)');
      fireConversion(8, AW_LABEL);
    });
  });

  // ── Checkout submit button (not a <form>, uses onclick) ──────
  // Watches for the Supabase order success screen appearing
  var successScreen = document.getElementById('successScreen');
  if (successScreen) {
    var observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (m) {
        if (m.type === 'attributes' && m.attributeName === 'style') {
          var visible = successScreen.style.display !== 'none' && successScreen.style.display !== '';
          if (visible) {
            console.log('[ConvTracking] Checkout order submitted — value: 8 THB');
            fireConversion(8, AW_LABEL);
            observer.disconnect(); // fire once per page load
          }
        }
      });
    });
    observer.observe(successScreen, { attributes: true });
  }

  console.log('[ConvTracking] Conversion tracking initialised on', window.location.pathname);
});
