// tactizen/app/static/js/page_utils.js

// Function to handle showing the message modal if it exists
function showMessageModal() {
    const messageModalElement = document.getElementById('messageModal');
    if (messageModalElement) {
        // Ensure Bootstrap's Modal class is available
        if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
            try {
                const messageModal = new bootstrap.Modal(messageModalElement);
                messageModal.show();
            } catch (e) {
                console.error("Error initializing or showing Bootstrap modal:", e);
            }
        } else {
            console.error("Bootstrap Modal component not found. Make sure Bootstrap JS is loaded before this script.");
        }
    }
}

// Wait for the DOM to be fully loaded before trying to show the modal
document.addEventListener('DOMContentLoaded', function() {
    showMessageModal();
    // You can add other page utility functions here and call them as needed
});