function improveText() {
    const text = document.getElementById("userText").value;

    fetch("/improve", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({text: text})
    })
    .then(res => res.json())
    .then(data => {
        document.getElementById("improveOutput").innerText = data.improved;
        document.getElementById("wordCount").innerText = data.word_count;
    });
}

function checkPlagiarism() {
    const text = document.getElementById("userText").value;

    fetch("/plagiarism", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({text: text})
    })
    .then(res => res.json())
    .then(data => {
        document.getElementById("plagiarismOutput").innerText =
            "Similarity Risk: " + data.similarity + "%";
    });
}