document.addEventListener("DOMContentLoaded", () => {

    const registerForm =
        document.getElementById("register-form");

    const errorBox =
        document.getElementById("error-message");

    const successBox =
        document.getElementById("success-message");

    registerForm.addEventListener(
        "submit",
        async (e) => {

            e.preventDefault();

            errorBox.style.display = "none";
            successBox.style.display = "none";

            const username =
                document
                .getElementById("username")
                .value
                .trim();

            const email =
                document
                .getElementById("email")
                .value
                .trim();

            const password =
                document
                .getElementById("password")
                .value;

            try {

                const response =
                    await fetch("/users", {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json"
                        },

                        body: JSON.stringify({
                            username,
                            email,
                            password
                        })
                    });

                const data =
                    await response.json();

                if (response.ok) {

                    successBox.textContent =
                        "Account created successfully. Redirecting to login...";

                    successBox.style.display =
                        "block";

                    registerForm.reset();

                    setTimeout(() => {

                        window.location.href = "/";

                    }, 2000);

                } else {

                    let message =
                        data.error ||
                        "Registration failed.";

                    if (data.fields) {

                        message +=
                            " Missing: " +
                            data.fields.join(", ");

                    }

                    errorBox.textContent =
                        message;

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