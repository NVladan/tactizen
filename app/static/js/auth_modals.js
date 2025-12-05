// app/static/js/auth_modals.js
// NOTE: This file might be obsolete as login/registration modals were removed
// in favor of the direct MetaMask connection flow.

// --- Avatar Preview Logic ---
// Function to update the avatar preview image in the registration modal
function previewAvatarModal(event) {
    const reader = new FileReader();
    reader.onload = function(){
        const output = document.getElementById('avatarPreviewModal');
        if (output) { // Check if the preview image element exists
           output.src = reader.result; // Set the preview source to the loaded file data
        }
    };
    // Read the selected file as a Data URL
    if (event.target.files[0]) {
        reader.readAsDataURL(event.target.files[0]);
    } else {
        // Optional: If no file is selected (e.g., user cancels), reset to default
        const output = document.getElementById('avatarPreviewModal');
        // Ensure you have a default placeholder image at this path
        if (output) {
           // Make sure you have a placeholder image at this location if you use this
           // output.src = "/static/images/default_avatar_placeholder.png";
        }
    }
}

// --- Main DOMContentLoaded Listener ---
// Ensures the script runs only after the full HTML document is loaded
document.addEventListener('DOMContentLoaded', function() {
    // console.log(">>> auth_modals.js: DOMContentLoaded event fired.");

    // --- Registration Success Check (Legacy - May no longer apply) ---
    const urlParams = new URLSearchParams(window.location.search);
    // console.log(">>> Checking for 'registered' URL parameter.");
    // console.log(">>> URL Search Params:", window.location.search);

    if (urlParams.has('registered') && urlParams.get('registered') === 'true') {
        // console.log(">>> 'registered=true' found! Preparing alert.");
        // Use modal alert if available, fallback to native alert
        if (typeof showSuccess === 'function') {
            showSuccess('Registration successful! You can now log in.');
        } else {
            alert('Registration successful! You can now log in.');
        }
        // Clean the URL parameter
        if (window.history.replaceState) {
            const cleanURL = window.location.pathname + window.location.hash; // Keep hash if present
            window.history.replaceState({path:cleanURL}, '', cleanURL);
            // console.log(">>> Cleaned URL history.");
        }
    } else {
         // console.log(">>> 'registered=true' NOT found.");
    }
    // --- END Registration Success Check ---

    // --- Forgot Password Modal Logic (Legacy - Likely unused) ---
    const resetRequestForm = document.getElementById('resetRequestForm');
    const resetPasswordForm = document.getElementById('resetPasswordForm');
    const resetStep1 = document.getElementById('reset-step-1');
    const resetStep2 = document.getElementById('reset-step-2');
    const resetRequestError = document.getElementById('reset-request-error'); // Div for step 1 errors
    const resetPasswordErrorMain = document.getElementById('reset-password-error-main'); // Div for step 2 main errors
    const resetUserEmail = document.getElementById('reset-user-email'); // Span to display user email in step 2
    const resetUserIdInput = document.getElementById('reset-user-id'); // Hidden input to store user ID
    const forgotPasswordModalEl = document.getElementById('forgotPasswordModal'); // The modal element itself

    // Initialize Bootstrap modal instance for programmatic control (hide/show)
    let modalInstance = null;
    if (forgotPasswordModalEl) {
         try {
            modalInstance = new bootstrap.Modal(forgotPasswordModalEl);
         } catch (e) {
             console.error("Failed to initialize Bootstrap modal for forgotPasswordModal:", e);
         }
    }

    // --- Handle Email Submission (Step 1: Request Password Reset) ---
    if (resetRequestForm) {
        resetRequestForm.addEventListener('submit', function(event) {
            event.preventDefault(); // Prevent default form submission
            // console.log("Reset Request Form Submitted");

            // --- UI Reset ---
            if(resetRequestError) resetRequestError.classList.add('d-none');
            const emailInput = document.getElementById('reset-email');
            const emailErrorDiv = document.getElementById('reset-email-error');
            if(emailInput) emailInput.classList.remove('is-invalid');
            if(emailErrorDiv) emailErrorDiv.textContent = '';

            // --- Prepare AJAX Request ---
            const formData = new FormData(resetRequestForm);
            const submitButton = document.getElementById('reset-request-submit');

            if (!submitButton) {
                 console.error("Submit button with ID 'reset-request-submit' not found!");
                 if(resetRequestError) {
                    resetRequestError.textContent = 'Page error. Please refresh.';
                    resetRequestError.classList.remove('d-none');
                 }
                 return;
            }

            const originalButtonValue = submitButton.value;
            submitButton.disabled = true;
            submitButton.value = 'Finding...';

            const csrfTokenInput = resetRequestForm.querySelector('input[name="csrf_token"]');
            const csrfToken = csrfTokenInput ? csrfTokenInput.value : null;
            // console.log("CSRF Token Found (Request):", csrfToken);

            if (!csrfToken) {
                console.error("CSRF Token input field not found in reset request form!");
                 if(resetRequestError) {
                   resetRequestError.textContent = 'Security token missing. Please refresh the page.';
                   resetRequestError.classList.remove('d-none');
                }
                 submitButton.disabled = false;
                 submitButton.value = originalButtonValue;
                return;
            }

            // Perform AJAX fetch request
            // console.log("Sending fetch request to:", resetRequestForm.action);
            fetch(resetRequestForm.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': csrfToken // Send CSRF token in header for security
                }
            })
            .then(response => {
                // console.log("Fetch response status (Request):", response.status);
                if (!response.ok) {
                    return response.text().then(text => {
                        try {
                            const errData = JSON.parse(text);
                            throw { status: response.status, data: errData }; // Throw structured error
                        } catch(e) {
                            throw new Error(`Server responded with status ${response.status}: ${text || 'No response body'}`);
                        }
                    });
                }
                return response.json();
            })
            .then(data => {
                // console.log("Parsed JSON data (Request):", data);
                if (data.success) {
                    // console.log("Success response from server (Request).");
                    if(resetUserEmail) resetUserEmail.textContent = data.email;
                    if(resetUserIdInput) resetUserIdInput.value = data.user_id;
                    if(resetPasswordForm) resetPasswordForm.action = `/auth/reset_password/${data.user_id}`; // Set action URL
                    if(resetStep1) resetStep1.style.display = 'none';
                    if(resetStep2) resetStep2.style.display = 'block';
                } else {
                    // console.log("Error response from server (Request):", data.error);
                    if(resetRequestError) {
                        resetRequestError.textContent = data.error || 'An unknown error occurred.';
                        resetRequestError.classList.remove('d-none');
                    }
                    if (data.errors && data.errors.email) {
                       if(emailInput) emailInput.classList.add('is-invalid');
                       if(emailErrorDiv) emailErrorDiv.textContent = data.errors.email;
                    }
                }
            })
            .catch(error => {
                console.error('Fetch Error (Request):', error);
                let errorMsg = 'An error occurred processing your request. Please try again.';
                if (error && error.status && error.data && error.data.error) {
                    errorMsg = `Error ${error.status}: ${error.data.error}`;
                    if (error.data.errors && error.data.errors.email) {
                       if(emailInput) emailInput.classList.add('is-invalid');
                       if(emailErrorDiv) emailErrorDiv.textContent = error.data.errors.email;
                     }
                }
                 if(resetRequestError) {
                    resetRequestError.textContent = errorMsg;
                    resetRequestError.classList.remove('d-none');
                 }
            })
            .finally(() => {
                // console.log("Fetch request finished (Request).");
                 submitButton.disabled = false;
                 submitButton.value = originalButtonValue;
            });
        });
    } // End Step 1 Form Handler

    // --- Handle Password Reset Submission (Step 2: Set New Password) ---
     if (resetPasswordForm) {
        resetPasswordForm.addEventListener('submit', function(event) {
            event.preventDefault(); // Prevent default form submission
            // console.log("Reset Password Form Submitted");

             // --- UI Reset ---
            if(resetPasswordErrorMain) resetPasswordErrorMain.classList.add('d-none');
            const passInput = document.getElementById('reset-password');
            const pass2Input = document.getElementById('reset-password2');
            const passErrorDiv = document.getElementById('reset-password-error');
            const pass2ErrorDiv = document.getElementById('reset-password2-error');
            if(passInput) passInput.classList.remove('is-invalid');
            if(pass2Input) pass2Input.classList.remove('is-invalid');
            if(passErrorDiv) passErrorDiv.textContent = '';
            if(pass2ErrorDiv) pass2ErrorDiv.textContent = '';

            // --- Prepare AJAX Request ---
            const formData = new FormData(resetPasswordForm);
            const submitButton = resetPasswordForm.querySelector('input[type="submit"]');
            const originalButtonValue = submitButton.value;
            submitButton.disabled = true;
            submitButton.value = 'Resetting...';

            const csrfTokenInput = resetPasswordForm.querySelector('input[name="csrf_token"]');
            const csrfToken = csrfTokenInput ? csrfTokenInput.value : null;
            // console.log("CSRF Token Found (Reset):", csrfToken);

             if (!csrfToken) {
                console.error("CSRF Token input field not found in reset password form!");
                if(resetPasswordErrorMain) {
                   resetPasswordErrorMain.textContent = 'Security token missing. Please refresh.';
                   resetPasswordErrorMain.classList.remove('d-none');
                }
                 submitButton.disabled = false;
                 submitButton.value = originalButtonValue;
                return;
            }

            // Perform AJAX fetch request (Action URL was set dynamically in step 1)
            // console.log("Sending fetch request to:", resetPasswordForm.action);
            fetch(resetPasswordForm.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': csrfToken // Send CSRF token in header
                }
             })
            .then(response => {
                // console.log("Fetch response status (Reset):", response.status);
                 if (!response.ok) {
                    return response.text().then(text => {
                         try {
                            const errData = JSON.parse(text);
                            throw { status: response.status, data: errData }; // Throw structured error
                        } catch(e) {
                            throw new Error(`Server responded with status ${response.status}: ${text || 'No response body'}`);
                        }
                    });
                }
                return response.json();
             })
            .then(data => {
                // console.log("Parsed JSON data (Reset):", data);
                if (data.success) {
                    // console.log("Success response from server (Reset).");
                    if (modalInstance) modalInstance.hide();
                    // Redirect using the URL provided by the server response
                    window.location.href = data.redirect_url || '/auth/login'; // Fallback just in case
                } else {
                     // console.log("Error response from server (Reset):", data.error);
                     if(resetPasswordErrorMain) {
                        resetPasswordErrorMain.textContent = data.error || 'Please correct the errors below.';
                        resetPasswordErrorMain.classList.remove('d-none');
                    }
                    // Display specific field errors if provided
                    if (data.errors) {
                        if(data.errors.password) {
                             if(passInput) passInput.classList.add('is-invalid');
                             if(passErrorDiv) passErrorDiv.textContent = data.errors.password;
                        }
                         if(data.errors.password2) {
                             if(pass2Input) pass2Input.classList.add('is-invalid');
                             if(pass2ErrorDiv) pass2ErrorDiv.textContent = data.errors.password2;
                        }
                    }
                }
            })
             .catch(error => {
                console.error('Fetch Error (Reset):', error);
                let errorMsg = 'An error occurred processing your request. Please try again.';
                 if (error && error.status && error.data && error.data.error) {
                    errorMsg = `Error ${error.status}: ${error.data.error}`;
                     if (error.data.errors) {
                        if(error.data.errors.password) {
                            if(passInput) passInput.classList.add('is-invalid');
                            if(passErrorDiv) passErrorDiv.textContent = error.data.errors.password;
                        }
                        if(error.data.errors.password2) {
                            if(pass2Input) pass2Input.classList.add('is-invalid');
                            if(pass2ErrorDiv) pass2ErrorDiv.textContent = error.data.errors.password2;
                        }
                    }
                }
                 if(resetPasswordErrorMain) {
                    resetPasswordErrorMain.textContent = errorMsg;
                    resetPasswordErrorMain.classList.remove('d-none');
                 }
            })
            .finally(() => {
                // console.log("Fetch request finished (Reset).");
                 submitButton.disabled = false;
                 submitButton.value = originalButtonValue;
            });
        });
     } // End Step 2 Form Handler

     // --- Reset Forgot Password modal to step 1 when it's closed ---
     if (forgotPasswordModalEl) {
         forgotPasswordModalEl.addEventListener('hidden.bs.modal', function () {
             // Reset visibility of steps
             if(resetStep1) resetStep1.style.display = 'block';
             if(resetStep2) resetStep2.style.display = 'none';
             // Reset the forms themselves
             if(resetRequestForm) resetRequestForm.reset();
             if(resetPasswordForm) resetPasswordForm.reset();
             // Clear general error messages
             if(resetRequestError) resetRequestError.classList.add('d-none');
             if(resetPasswordErrorMain) resetPasswordErrorMain.classList.add('d-none');
             // Clear validation states and specific errors from input fields
             const emailInput = document.getElementById('reset-email');
             const passInput = document.getElementById('reset-password');
             const pass2Input = document.getElementById('reset-password2');
             const emailErrorDiv = document.getElementById('reset-email-error');
             const passErrorDiv = document.getElementById('reset-password-error');
             const pass2ErrorDiv = document.getElementById('reset-password2-error');
             if(emailInput) emailInput.classList.remove('is-invalid');
             if(passInput) passInput.classList.remove('is-invalid');
             if(pass2Input) pass2Input.classList.remove('is-invalid');
             if(emailErrorDiv) emailErrorDiv.textContent = '';
             if(passErrorDiv) passErrorDiv.textContent = '';
             if(pass2ErrorDiv) pass2ErrorDiv.textContent = '';
         });
     }
     // --- END Reset Forgot Password Modal Logic ---

}); // End DOMContentLoaded Listener