const token = localStorage.getItem("recipe_token");
if (!token) location.href = "/login";

const f = document.getElementById("recipe-form");
const err = document.getElementById("form-error");
const headers = {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${token}`,
};

if (window.recipeId) {
    document.getElementById("form-title").textContent = "Edit recipe";

    fetch(`/recipes/${window.recipeId}`, {headers})
        .then((r) => {
            if (!r.ok) throw Error("Recipe unavailable");
            return r.json();
        })
        .then((d) => {
            for (const k of ["title", "ingredients", "instructions"]) {
                f.elements[k].value = d[k] || "";
            }
            f.elements.is_public.checked = d.is_public;
        })
        .catch((e) => {
            err.textContent = e.message;
            err.style.display = "block";
        });
} else {
    document.getElementById("form-title").textContent = "Add a recipe";
}

f.addEventListener("submit", async (e) => {
    e.preventDefault();

    const data = Object.fromEntries(new FormData(f));
    data.is_public = f.elements.is_public.checked;

    const url = window.recipeId ? `/recipes/${window.recipeId}` : "/recipes";
    const method = window.recipeId ? "PATCH" : "POST";

    let r = await fetch(url, {
        method,
        headers,
        body: JSON.stringify(data),
    });

    if (!r.ok) {
        let d = await r.json();

        if (window.recipeId && r.status === 403) {
            err.textContent = "You can only edit your own recipes.";
            err.style.display = "block";

            if (confirm("Send these proposed changes to an admin for approval?")) {
                r = await fetch(`/recipes/${window.recipeId}/approval-requests`, {
                    method: "POST",
                    headers,
                    body: JSON.stringify({
                        action: "edit",
                        payload: data,
                    }),
                });
                d = await r.json();

                if (r.ok) {
                    alert(d.message);
                    location.href = "/dashboard";
                    return;
                }
            }
        }

        if (!r.ok) {
            err.textContent = d.message || d.error || "Unable to save recipe";
            err.style.display = "block";
            return;
        }
    }

    location.href = "/dashboard";
});
