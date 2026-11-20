const token=localStorage.getItem('recipe_token');

if(!token)location.href='/login';

const form=document.getElementById('profile-form');

const headers={
    'Content-Type':'application/json',
    'Authorization':`Bearer ${token}`
};

fetch('/profile/data',
    {headers}).then(r=>{if(!r.ok)location.href='/login';
    return r.json()}).then(d=>Object.keys(d).forEach(k=>{
        if(form.elements[k])form.elements[k].value=d[k]||''}));

form.addEventListener('submit',
    async e=>{e.preventDefault();
        
    const d=Object.fromEntries(new FormData(form));

    const r=await fetch('/profile/data',
        {method:'PUT',headers,body:JSON.stringify(d)});
        document.getElementById('profile-message').textContent=r.ok?'Profile saved.':'Could not save profile.';
        document.getElementById('profile-message').style.display='block'});
