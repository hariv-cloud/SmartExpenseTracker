/* Budget progress bar */

const budgetProgressBar = document.querySelector(".budget-progress-fill");

if (budgetProgressBar) {
    const progress = parseFloat(
        budgetProgressBar.dataset.progress || "0"
    );

    budgetProgressBar.style.width = `${progress}%`;
}