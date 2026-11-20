const token=localStorage.getItem('recipe_token'),
headers={'Content-Type':'application/json','Authorization':`Bearer ${token}`},
box=document.getElementById('admin-content');
async function api(path,options={}){
    const r=await fetch(path,
        {...options,
            
            headers:{...headers,
                ...options.headers}
            });
        const d=await r.json();
        
        if(!r.ok){
            document.getElementById('admin-message').textContent=d.error||'Admin access required';
            document.getElementById('admin-message').style.display='block';
            throw Error(d.error)
        }return d
    }
    async function loadUsers()
    {
        try{
            let users=await api('/admin/users');
            box.innerHTML='<h2>Registered people</h2>'+users.map(u=>`<div class="admin-row"><span>${u.username} · ${u.email}${u.is_admin?' · Admin':''}</span><button class="delete-btn" onclick="removeUser(${u.id})">Remove</button></div>`).join('')+'<h3>Add a person</h3><form id="add-user" class="inline-form"><input class="form-control" name="username" placeholder="Username" required><input class="form-control" name="email" type="email" placeholder="Email" required><input class="form-control" name="password" type="password" placeholder="Temporary password" required><label><input type="checkbox" name="is_admin"> Admin</label><button class="login-btn">Add person</button></form>';document.getElementById('add-user').onsubmit=async e=>{e.preventDefault();let d=Object.fromEntries(new FormData(e.target));d.is_admin=e.target.is_admin.checked;await api('/admin/users',{method:'POST',body:JSON.stringify(d)});loadUsers()}}catch{}}

async function removeUser(id){
    if(confirm('Remove this account and its owned recipes?')){
        try{await api(`/admin/users/${id}`,{method:'DELETE'});
        loadUsers()}catch{}
    }}

async function loadRecipes(){
    try{
        let rows=await api('/admin/recipes');
        box.innerHTML='<h2>Recipe database</h2>'+rows.map(r=>`<div class="admin-row"><span>#${r.id} · ${r.title} · ${r.is_public?'Public':'Private'}</span><button onclick="editAdminRecipe(${r.id})">Edit</button><button class="delete-btn" onclick="deleteAdminRecipe(${r.id})">Delete</button></div>`).join('')+'<button onclick="editAdminRecipe(null)">Add recipe</button><div id="recipe-editor"></div>'}catch{}}

async function editAdminRecipe(id){
    let data={};
    if(id){
        data=(await api('/admin/recipes')).find(r=>r.id===id)
    }
    console.log(data);
    document.getElementById('recipe-editor').innerHTML=`<h3>${id?'Edit':'Add'} recipe</h3><form id="recipe-form" class="form-panel"><input class="form-control" name="title" placeholder="Title" required><textarea class="form-control" name="ingredients" placeholder="Ingredients" required></textarea><textarea class="form-control" name="instructions" placeholder="Instructions"></textarea><input class="form-control" name="user_id" type="number" placeholder="Owner user ID (optional)"><label><input name="is_public" type="checkbox"> Public</label><button class="login-btn">Save recipe</button></form>`;let f=document.getElementById('recipe-form');if(data)for(let k of ['title','ingredients','instructions','user_id'])f.elements[k].value=data[k]||'';f.elements.is_public.checked=!!data.is_public;f.onsubmit=async e=>{e.preventDefault();let d=Object.fromEntries(new FormData(f));d.is_public=f.elements.is_public.checked;d.user_id=d.user_id?Number(d.user_id):null;await api(id?`/admin/recipes/${id}`:'/admin/recipes',{method:id?'PUT':'POST',body:JSON.stringify(d)});loadRecipes()}}

async function deleteAdminRecipe(id){
    if(confirm('Permanently delete this recipe?')){
        await api(`/admin/recipes/${id}`,
            {method:'DELETE'});
            loadRecipes()
        }}
    loadUsers();

async function loadRequests(){try{const rows=await api('/admin/approval-requests');box.innerHTML='<h2>Pending approval requests</h2>';if(!rows.length){box.insertAdjacentHTML('beforeend','<p>No requests are waiting.</p>');return}for(const req of rows){const card=document.createElement('article');card.className='recipe-card';const payload=JSON.parse(req.payload||'{}');const title=document.createElement('h3');title.textContent=`${req.action==='delete'?'Deletion':'Edit'} request: ${req.recipe_title}`;const by=document.createElement('p');by.textContent=`Requested by ${req.requester} · ${req.created_at}`;card.append(title,by);if(req.action==='edit'){const detail=document.createElement('pre');detail.textContent=JSON.stringify(payload,null,2);card.append(detail)}for(const decision of ['approve','reject']){const b=document.createElement('button');b.textContent=decision==='approve'?'Approve':'Reject';b.className=decision==='reject'?'delete-btn':'';b.onclick=async()=>{await api(`/admin/approval-requests/${req.id}`,{method:'POST',body:JSON.stringify({decision})});loadRequests()};card.append(b)}box.append(card)}}catch{}}
