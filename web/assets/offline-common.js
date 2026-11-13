/* Offline replay primitives only: no accounts, server APIs, fixtures or bots. */
window.Arena=(()=>{
  const paths={play:'m8 4 13 8-13 8z',pause:'M8 4v16M16 4v16',back:'m19 4-12 8 12 8V4ZM5 4v16'};
  const icon=name=>`<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]||paths.play}"/></svg>`;
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fa=n=>new Intl.NumberFormat('fa-IR').format(n??0);
  const reasons={completed:'پایان ۳۰ انتخاب',turn_timeout:'پایان زمان نوبت',total_timeout:'پایان زمان مجموع',total_cpu_timeout:'پایان زمان پردازش',invalid_output:'خروجی نامعتبر',extra_output:'خروجی اضافه',inactive_output:'خروجی در نوبت حریف',stdout_limit:'خروجی بیش از حد',stderr_limit:'گزارش خطای بیش از حد',premature_exit:'بسته شدن زودهنگام کد',runtime_error:'خطای اجرای کد',exit_timeout:'کد پس از پایان بسته نشد'};
  let timer;
  function toast(message,error=false){const el=document.getElementById('toast');el.textContent=message;el.className='show'+(error?' error':'');clearTimeout(timer);timer=setTimeout(()=>el.className='',6000)}
  return{icon,esc,fa,reasons,toast};
})();
