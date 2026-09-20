(function () {
  "use strict";

  document.querySelectorAll(".faq-q").forEach(function (question, index) {
    var answer = question.nextElementSibling;
    var answerId = "faq-answer-" + (index + 1);

    question.setAttribute("role", "button");
    question.setAttribute("tabindex", "0");
    question.setAttribute(
      "aria-expanded",
      question.parentElement.classList.contains("open") ? "true" : "false"
    );

    if (answer) {
      answer.id = answerId;
      question.setAttribute("aria-controls", answerId);
    }

    question.addEventListener("click", function () {
      question.setAttribute(
        "aria-expanded",
        question.parentElement.classList.contains("open") ? "true" : "false"
      );
    });

    question.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        question.click();
      }
    });
  });
}());
