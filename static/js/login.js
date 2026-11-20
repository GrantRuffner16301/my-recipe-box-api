document.addEventListener("DOMContentLoaded", () => {

    const loginForm =
        document.getElementById("login-form");

    const errorBox =
        document.getElementById("error-message");

    loginForm.addEventListener(
        "submit",
        async (e) => {

            e.preventDefault();

            errorBox.style.display = "none";

            const username =
                document
                .getElementById("username")
                .value
                .trim();

            const password =
                document
                .getElementById("password")
                .value;

            try {

                const response =
                    await fetch("/login", {

                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body: JSON.stringify({
                            username,
                            password
                        })

                    });

                const data =
                    await response.json();

                if (response.ok) {

                    localStorage.setItem(
                        "recipe_token",
                        data.token
                    );

                    localStorage.setItem(
                        "recipe_user",
                        data.username
                    );

                    localStorage.setItem(
                        "recipe_user_id",
                        data.id
                    );

                    window.location.href =
                        "/dashboard";

                } else {

                    errorBox.textContent =
                        data.message ||
                        data.error ||
                        "Login failed.";

                    errorBox.style.display =
                        "block";
                }

            } catch (error) {

                errorBox.textContent =
                    "Unable to connect to server.";

                errorBox.style.display =
                    "block";

                console.error(error);
            }
        }
    );

});