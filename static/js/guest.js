let publicRecipes=[];const grid=document.getElementById('recipe-grid');
fetch('/recipes/public').then(r=>r.json()).
then(rows=>{publicRecipes=rows;render();});
function render(){
    const q=document.getElementById('recipe-search').value.toLowerCase();
    grid.innerHTML='';
    publicRecipes.filter(r=>`${r.title} ${r.ingredients} ${r.instructions}`.
        toLowerCase().includes(q)).forEach(r=>{const card=document.createElement('article');
            card.className='recipe-card';
            for(const [tag,text] of [['h3',r.title],
                ['p',`Ingredients: ${r.ingredients}`],
                ['p',`Instructions: ${r.instructions||'—'}`]]){
                    const e=document.createElement(tag);
                    e.textContent=text;card.append(e)}
                    grid.append(card)});
                    if(!grid.children.length)grid.textContent='No public recipes match that search.'}
document.getElementById('recipe-search').addEventListener('input',render);
