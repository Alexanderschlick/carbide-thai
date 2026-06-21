(function(){
  var SB='https://ltupwgytuayzopnsdvpc.supabase.co';
  var SK='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx0dXB3Z3l0dWF5em9wbnNkdnBjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI5OTg5MzIsImV4cCI6MjA4ODU3NDkzMn0.bwPshMqh_NZc7MBSzbzbezOeMWm3e81iz3rJJSrrZhE';
  var sid=sessionStorage.getItem('tc_sid');
  if(!sid){sid=crypto.randomUUID();sessionStorage.setItem('tc_sid',sid);}
  var params=new URLSearchParams(location.search);
  var utm={source:params.get('utm_source')||'',medium:params.get('utm_medium')||'',campaign:params.get('utm_campaign')||'',term:params.get('utm_term')||''};
  var ref=document.referrer||'';
  var device=/Mobi|Android/i.test(navigator.userAgent)?'mobile':'desktop';
  var pageStart=Date.now();
  var maxScroll=0;
  var scrollTick;
  window.addEventListener('scroll',function(){clearTimeout(scrollTick);scrollTick=setTimeout(function(){var h=document.documentElement.scrollHeight-window.innerHeight;if(h>0){var pct=Math.round((window.scrollY/h)*100);if(pct>maxScroll)maxScroll=pct;}},200);},{passive:true});
  function sbInsert(table,data){fetch(SB+'/rest/v1/'+table,{method:'POST',headers:{'Content-Type':'application/json','apikey':SK,'Authorization':'Bearer '+SK,'Prefer':'return=minimal'},body:JSON.stringify(data)}).catch(function(){});}
  function trackEvent(type,data){sbInsert('conversion_events',{session_id:sid,event_type:type,event_data:data||{},page:location.pathname,utm_source:utm.source,utm_medium:utm.medium,utm_campaign:utm.campaign,utm_term:utm.term,device:device});}
  sbInsert('page_views',{page:location.pathname+location.search,utm_source:utm.source,utm_medium:utm.medium,utm_campaign:utm.campaign,utm_term:utm.term,referrer:ref,device:device,session_id:sid});
  trackEvent('page_view',{referrer:ref});
  function sendExit(){var t=Math.round((Date.now()-pageStart)/1000);var p=JSON.stringify({session_id:sid,event_type:'page_exit',event_data:{scroll_depth:maxScroll,time_on_page:t},page:location.pathname,device:device});if(navigator.sendBeacon)navigator.sendBeacon(SB+'/rest/v1/conversion_events',new Blob([p],{type:'application/json'}));}
  document.addEventListener('visibilitychange',function(){if(document.visibilityState==='hidden')sendExit();});
  document.addEventListener('click',function(e){var el=e.target.closest('a[href],button,.cta-btn,.btn');if(!el)return;var text=(el.textContent||'').trim().substring(0,50);var href=el.getAttribute('href')||'';if(el.classList.contains('cta-btn')||el.classList.contains('btn')||href.includes('sell')||href.includes('checkout')||href.includes('line.me'))trackEvent('cta_click',{text:text,href:href});if(href.includes('line.me')||href.includes('lin.ee'))trackEvent('line_click',{text:text});if(href.startsWith('tel:'))trackEvent('phone_click',{text:text});});
  document.addEventListener('click',function(e){if(e.target.closest('#chat-widget-btn,#chat-toggle,.chat-toggle,[onclick*="chat"]'))trackEvent('chat_open',{});});
  window.tcTrack=trackEvent;
})();
