const input = document.getElementById("inputText");

function updateCounts() {
    const text = input.value.trim();
    const words = text ? text.split(/\s+/).length : 0;
    document.getElementById("wordCount").innerText = words;
    document.getElementById("charCount").innerText = text.length;
}

function improveText() {

    const text = input.value;
    const spinner = document.getElementById("spinner");

    spinner.style.display = "block";

    fetch("/improve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text })
    })
    .then(res => res.json())
    .then(data => {

        spinner.style.display = "none";

        document.getElementById("corrected").innerText = data.corrected || "";
        document.getElementById("enhanced").innerText = data.enhanced || "";
        animateScores();
        addToHistory(text);
    })
    .catch(() => {
        spinner.style.display = "none";
    });
}

function animateScores() {
    const ids = ["grammarScore","clarityScore","professionalScore","overallScore"];
    ids.forEach(id => {
        let el = document.getElementById(id);
        let value = Math.floor(Math.random()*30+70);
        let count = 0;
        let interval = setInterval(() => {
            count++;
            el.innerText = count;
            if(count >= value) clearInterval(interval);
        }, 10);
    });
}

function checkPlagiarism() {
    const text = input.value;

    fetch("/plagiarism", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text })
    })
    .then(res => res.json())
    .then(data => {
        document.getElementById("plagiarismResult").innerText = data.similarity + "%";
    });
}

function addToHistory(text) {
    const historyList = document.getElementById("historyList");
    const li = document.createElement("li");
    li.innerText = text;
    historyList.prepend(li);

    if (historyList.children.length > 5) {
        historyList.removeChild(historyList.lastChild);
    }
}

document.getElementById("featuresBtn").onclick = function() {
    document.getElementById("featuresSection").classList.toggle("hidden-section");
};

document.getElementById("studioBtn").onclick = function() {
    window.scrollTo({ top: document.getElementById("studioSection").offsetTop - 80, behavior: "smooth" });
};

document.getElementById("recentBtn").onclick = function() {
    document.getElementById("recentPanel").classList.toggle("active");
    document.getElementById("overlay").classList.toggle("active");
};

document.getElementById("overlay").onclick = function() {
    document.getElementById("recentPanel").classList.remove("active");
    document.getElementById("overlay").classList.remove("active");
};
function loadHistory(){

fetch("/history")
.then(res => res.json())
.then(data => {

const historyList = document.getElementById("historyList")

historyList.innerHTML=""

data.forEach(item => {

let li = document.createElement("li")

li.innerText = item

historyList.appendChild(li)

})

})

}

window.onload = loadHistory
function logoutUser(){

fetch("/logout")
.then(res => res.json())
.then(data => {

window.location.href="/"

})

}
