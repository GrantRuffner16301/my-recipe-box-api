const token=localStorage.getItem('recipe_token');

if(!token)location.href='/login';

const headers={'Content-Type':'application/json','Authorization':`Bearer ${token}`};

area=document.getElementById('owner-requests');

async function load(){
    const r=await fetch('/owner/approval-requests',{headers});
    if(!r.ok){
        area.textContent='Unable to load your requests.';
        return
    }
    const rows=await r.json();

    area.innerHTML='';

    if(!rows.length){
        area.textContent='No pending requests for your recipes.';
        return
    }
    for(const q of rows){
        const card=document.createElement('article');
        card.className='recipe-card';
        const title=document.createElement('h3');
        title.textContent=`${q.action==='delete'?'Deletion':'Edit'} suggestion for ${q.recipe_title}`;
        const from=document.createElement('p');from.textContent=`From ${q.requester} · ${q.created_at}`;
        card.append(title,from);
        if(q.action==='edit'){
            const details=document.createElement('pre');
            details.textContent=JSON.stringify(JSON.parse(q.payload||'{}'),null,2);
            card.append(details)
        }
        for(const decision of ['approve','reject']){
            const btn=document.createElement('button');
            btn.textContent=decision==='approve'?'Apply change':'Reject';
            btn.className=decision==='reject'?'delete-btn':'';

            btn.onclick=async()=>{const response=await fetch(`/owner/approval-requests/${q.id}`,
                    {method:'POST',headers,body:JSON.stringify({decision})});

            const data=await response.json();

            if(!response.ok){alert(data.error||'Could not process request');
                return}load()};

            card.append(btn)
        }
        area.append(card)
    }
}
load();
