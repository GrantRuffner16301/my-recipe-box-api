const token = localStorage.getItem("recipe_token");
const username = localStorage.getItem("recipe_user");

if (!token) {
    window.location.href = "/";
}

const recipeGrid =
    document.getElementById("recipe-grid");

const recipeCount =
    document.getElementById("recipe-count");

const publicCount =
    document.getElementById("public-count");

const privateCount =
    document.getElementById("private-count");

const welcomeUser =
    document.getElementById("welcome-user");

if (welcomeUser && username) {
    welcomeUser.textContent =
        `Welcome Back, ${username}`;
}

fetch('/me', {headers: authHeaders()}).then(r=>r.ok?r.json():null).then(u=>{if(u?.is_admin)document.getElementById('admin-link').style.display='flex';if(u)document.getElementById('owner-link').style.display='flex'});
fetch('/notifications',{headers:authHeaders()}).then(r=>r.ok?r.json():[]).then(items=>{const area=document.getElementById('notifications');items.forEach(n=>{const item=document.createElement('p');item.className='notification';item.textContent=n.message;area.append(item)})});

async function loadMyRecipes() {

    try {

        const response =
            await fetch("/recipes", {
                headers: authHeaders()
            });

        const recipes =
            await response.json();

        recipeGrid.innerHTML = "";

        let publicRecipes = 0;
        let privateRecipes = 0;

        recipes.forEach(recipe => {

            if (recipe.is_public) {
                publicRecipes++;
            } else {
                privateRecipes++;
            }

            recipeGrid.insertAdjacentHTML(
                "beforeend",

                `
                <div class="recipe-card">

                    <h3>${recipe.title}</h3>

                    <p>
                        <strong>Ingredients:</strong>
                        ${recipe.ingredients}
                    </p>

                    <p>
                        <strong>Instructions:</strong>
                        ${recipe.instructions || ""}
                    </p>

                    <p>
                        <strong>Visibility:</strong>
                        ${recipe.is_public
                            ? "Public"
                            : "Private"}
                    </p>

                    <div class="recipe-buttons">

                        <button
                            class="edit-btn"
                            onclick="editRecipe(${recipe.id})">

                            Edit

                        </button>

                        <button
                            class="delete-btn"
                            onclick="deleteRecipe(${recipe.id})">

                            Delete

                        </button>

                    </div>

                </div>
                `
            );
        });

        recipeCount.textContent =
            recipes.length;

        publicCount.textContent =
            publicRecipes;

        privateCount.textContent =
            privateRecipes;

    }
    catch(error) {

        console.error(error);

        recipeGrid.innerHTML =
        `
            <div class="recipe-card">

                <h3>Connection Error</h3>

                <p>
                    Unable to load recipes.
                </p>

            </div>
        `;
    }
}

async function loadPublicRecipes() {

    try {

        const response =
            await fetch("/recipes/public");

        const recipes =
            await response.json();

        recipeGrid.innerHTML = "";

        recipes.forEach(recipe => {

            recipeGrid.insertAdjacentHTML(
                "beforeend",

                `
                <div class="recipe-card">

                    <h3>${recipe.title}</h3>

                    <p>
                        <strong>Ingredients:</strong>
                        ${recipe.ingredients}
                    </p>

                    <p>
                        <strong>Instructions:</strong>
                        ${recipe.instructions || ""}
                    </p>

                </div>
                `
            );
        });

    }
    catch(error) {

        console.error(error);

    }
}

async function loadAllRecipes(){const response=await fetch('/recipes',{headers:authHeaders()});const recipes=await response.json();recipeGrid.innerHTML='';recipes.forEach(recipe=>{const card=document.createElement('article');card.className='recipe-card';card.innerHTML=`<h3></h3><p class="owner-line"></p><p class="ingredient-line"></p><p class="instruction-line"></p><p class="visibility-line"></p><div class="recipe-buttons"><button class="edit-btn">Edit</button><button class="delete-btn">Delete</button></div>`;card.querySelector('h3').textContent=recipe.title;card.querySelector('.ingredient-line').textContent=`Ingredients: ${recipe.ingredients}`;card.querySelector('.instruction-line').textContent=`Instructions: ${recipe.instructions||''}`;card.querySelector('.visibility-line').textContent=recipe.is_public?'Public':'Private';card.querySelector('.edit-btn').onclick=()=>editRecipe(recipe.id);card.querySelector('.delete-btn').onclick=()=>deleteRecipe(recipe.id);recipeGrid.append(card)});}

function showCreateRecipe() {

    window.location.href =
        "/recipe/new";
}

function editRecipe(recipeId) {

    window.location.href =
        `/recipe/${recipeId}`;
}

async function deleteRecipe(recipeId) {

    const confirmed =
        confirm(
            "Delete this recipe?"
        );

    if (!confirmed) {
        return;
    }

    try {

        let response = await fetch(`/recipes/${recipeId}`, {method:"DELETE", headers:authHeaders()});

        const data =
            await response.json();

        if (!response.ok) {
            if(response.status===403){
                const approved=confirm("You can only delete your own recipes. Would you like to send this deletion to an admin for approval?");
                if(!approved)return;
                response=await fetch(`/recipes/${recipeId}/approval-requests`,{method:"POST",headers:authHeaders(),body:JSON.stringify({action:"delete"})});
            }
            if(!response.ok){const retry=await response.json();alert(retry.message||retry.error||"Unable to delete recipe.");return;}
            const result=await response.json();if(result.message)alert(result.message);
        }

        loadMyRecipes();

    }
    catch(error) {

        console.error(error);

        alert(
            "Server error while deleting recipe."
        );
    }
}

function logout() {

    localStorage.removeItem(
        "recipe_token"
    );

    localStorage.removeItem(
        "recipe_user"
    );

    localStorage.removeItem(
        "recipe_user_id"
    );

    window.location.href = "/";
}

const logoutButton =
    document.getElementById(
        "logout-btn"
    );

if (logoutButton) {

    logoutButton.addEventListener(
        "click",
        logout
    );
}

loadMyRecipes();
