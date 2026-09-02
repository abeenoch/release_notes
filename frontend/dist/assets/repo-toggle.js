(function(){
'use strict';
var tkn=localStorage.getItem('arn_token');
if(!tkn)return;

function api(p,o){
 o=o||{};
 var h={'Authorization':'Bearer '+tkn,'Content-Type':'application/json'};
 if(o.headers) Object.assign(h,o.headers);
 return fetch('/api'+p,{method:o.method||'GET',headers:h,body:o.body}).then(function(r){
  return r.ok ? r.json() : r.json().then(function(d){throw new Error(d.detail||'Request failed');});
 });
}

var modal=null;

function showModal(repos){
 if(modal) modal.remove();
 var added=repos.filter(function(r){return r.already_added;});
 var fresh=repos.filter(function(r){return !r.already_added;});

 var ov=document.createElement('div');
 ov.id='ac-import-modal';
 ov.style.cssText='position:fixed;top:0;left:0;right:0;bottom:0;z-index:999999;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;padding:24px;font-family:system-ui,sans-serif;';

 var box=document.createElement('div');
 box.style.cssText='background:white;border-radius:16px;width:680px;max-height:90vh;display:flex;flex-direction:column;box-shadow:0 25px 60px rgba(0,0,0,0.3);';

 var hdr=document.createElement('div');
 hdr.style.cssText='display:flex;align-items:center;justify-content:space-between;padding:20px 24px;border-bottom:1px solid #e4e4e7;flex-shrink:0;';
 hdr.innerHTML='<h2 style="margin:0;font-size:18px;font-weight:600;color:#18181b;">Import Repositories</h2>';
 var xb=document.createElement('button');xb.textContent='X';
 xb.style.cssText='background:none;border:none;font-size:18px;color:#71717a;cursor:pointer;padding:4px 8px;';
 xb.onclick=function(){ov.remove();modal=null;};
 hdr.appendChild(xb);box.appendChild(hdr);

 var info=document.createElement('div');
 info.style.cssText='padding:10px 24px;font-size:13px;color:#71717a;background:#f4f4f5;border-bottom:1px solid #e4e4e7;flex-shrink:0;';
 info.textContent='Select repos to enable for changelog auto-generation.';
 box.appendChild(info);

 var list=document.createElement('div');
 list.style.cssText='overflow-y:auto;flex:1;overflow-x:hidden;';

 function mkItem(data,isAdded){
  var row=document.createElement('div');
  row.style.cssText='display:flex;align-items:center;gap:10px;padding:10px 24px;border-bottom:1px solid #f4f4f5;';
  var cb=document.createElement('input');cb.type='checkbox';
  cb.dataset.fullname=data.full_name;
  cb.style.cssText='width:18px;height:18px;accent-color:#18181b;cursor:pointer;flex-shrink:0;margin:0;';
  if(isAdded){cb.checked=true;cb.disabled=true;row.style.opacity='0.6';}
  else {cb.checked=false;}
  var txt=document.createElement('div');txt.style.cssText='flex:1;min-width:0;';
  var nm=document.createElement('div');nm.style.cssText='font-size:14px;font-weight:500;color:#18181b;';
  nm.textContent=data.full_name;
  var ds=document.createElement('div');ds.style.cssText='font-size:12px;color:#71717a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
  ds.textContent=data.description||(data.is_private?'Private':'Public');
  txt.appendChild(nm);txt.appendChild(ds);
  var tag=document.createElement('span');
  tag.style.cssText='font-size:11px;font-weight:500;padding:2px 8px;border-radius:999px;flex-shrink:0;';
  if(isAdded){tag.textContent='Active';tag.style.background='#dcfce7';tag.style.color='#166534';}
  else if(data.is_private){tag.textContent='Private';tag.style.background='#fef3c7';tag.style.color='#92400e';}
  else {tag.textContent='Public';tag.style.background='#f0f0f0';tag.style.color='#52525b';}
  row.appendChild(cb);row.appendChild(txt);row.appendChild(tag);return row;
 }

 if(added.length){
  var s1=document.createElement('div');
  s1.style.cssText='padding:12px 24px 4px;font-size:11px;font-weight:600;color:#71717a;text-transform:uppercase;';
  s1.textContent='Already imported ('+added.length+')';
  list.appendChild(s1);added.forEach(function(r){list.appendChild(mkItem(r,true));});
 }
 if(fresh.length){
  var s2=document.createElement('div');
  s2.style.cssText='padding:12px 24px 4px;font-size:11px;font-weight:600;color:#71717a;text-transform:uppercase;';
  s2.textContent='Available ('+fresh.length+')';
  list.appendChild(s2);fresh.forEach(function(r){list.appendChild(mkItem(r,false));});
 }
 box.appendChild(list);

 var ft=document.createElement('div');
 ft.style.cssText='display:flex;align-items:center;justify-content:space-between;padding:16px 24px;border-top:1px solid #e4e4e7;flex-shrink:0;';
 var cnt=document.createElement('span');cnt.style.cssText='font-size:13px;color:#71717a;';
 ft.appendChild(cnt);

 var ib=document.createElement('button');
 ib.textContent='Import Selected';ib.disabled=true;
 ib.style.cssText='background:#18181b;color:white;border:none;padding:10px 24px;border-radius:10px;font-size:14px;font-weight:500;cursor:pointer;opacity:0.5;';

 function upd(){
  var c=list.querySelectorAll('input[type=checkbox]:not([disabled]):checked').length;
  cnt.textContent=c+' repo'+(c!==1?'s':'')+' selected';
  ib.disabled=(c===0);ib.style.opacity=(c===0)?'0.5':'1';
 }

 ib.onclick=function(e){
  e.stopPropagation();
  var sel=[];
  list.querySelectorAll('input[type=checkbox]:not([disabled]):checked').forEach(function(cb){sel.push(cb.dataset.fullname);});
  if(!sel.length)return;
  ib.disabled=true;ib.textContent='Importing...';
  fetch('/api/repos/import',{
   method:'POST',
   headers:{'Authorization':'Bearer '+tkn,'Content-Type':'application/json'},
   body:JSON.stringify({full_names:sel})
  }).then(function(r){
   if(!r.ok)return r.json().then(function(d){throw new Error(d.detail||'failed');});
   return r.json();
  }).then(function(){
   ov.remove();modal=null;
   setTimeout(function(){location.reload();},200);
  }).catch(function(err){
   alert('Import failed: '+err.message);
   ib.disabled=false;ib.textContent='Import Selected';
  });
 };

 ft.appendChild(cnt);ft.appendChild(ib);box.appendChild(ft);ov.appendChild(box);document.body.appendChild(ov);
 modal=ov;upd();

 list.addEventListener('change',function(e){if(e.target.type==='checkbox')upd();});
}

// Intercept Sync from GitHub clicks BEFORE React (capture phase)
document.addEventListener('click',function(e){
 if(document.getElementById('ac-import-modal')) return;
 var btn=e.target.closest('button');
 if(!btn) return;
 if(btn.textContent.trim()!=='Sync from GitHub') return;
 e.preventDefault();
 e.stopPropagation();
 btn.disabled=true;btn.textContent='Loading...';
 api('/repos/preview',{method:'POST'}).then(function(data){
  if(data.repos&&data.repos.length)showModal(data.repos);
  else alert('No repos found on GitHub.');
  btn.disabled=false;btn.textContent='Sync from GitHub';
 }).catch(function(err){
  alert('Failed: '+err.message);
  btn.disabled=false;btn.textContent='Sync from GitHub';
 });
},true);

// ── Refresh changelog list when the user navigates back to the page ──
// This re-fetches the changelogs list whenever the page becomes visible
// (after a tab switch, page back, or window focus) — fixes the
// "stays Queued" issue when the user returns to a repo detail page.
document.addEventListener('visibilitychange',function(){
 if(!document.hidden) refreshChangelogs();
});
window.addEventListener('focus',function(){
 refreshChangelogs();
});

function refreshChangelogs(){
 // Only run on a repo detail page (URL matches /repos/<id>)
 var m=window.location.pathname.match(/^\/repos\/([a-f0-9-]+)$/);
 if(!m) return;
 var repoId=m[1];
 // Trigger the React component to re-fetch by clicking anywhere on the page
 // that triggers a re-render. Easier: just reload the changelogs list API
 // and dispatch a custom event. The component's useEffect won't re-run, but
 // we can simulate the polling by calling the same fetch it uses.
 var btns=document.querySelectorAll('button');
 for(var i=0;i<btns.length;i++){
  var b=btns[i];
  if(b.textContent.trim()==='Refresh'||b.textContent.trim()==='Reload'){
   b.click();
   return;
  }
 }
 // Fallback: simply navigate to refresh the page
 // (only if we're seeing a "Queued" or "Generating" state)
 var statusEls=document.querySelectorAll('*');
 for(var j=0;j<statusEls.length;j++){
  var t=statusEls[j].textContent;
  if(t==='Queued'||t==='Generating...'){
   setTimeout(function(){window.location.reload();},100);
   return;
  }
 }
}

})();
