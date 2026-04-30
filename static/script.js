/* ---------------- THEME TOGGLE + DOWNLOAD RESULT ---------------- */

document.addEventListener("DOMContentLoaded", function(){
    applySavedTheme();
});

function applySavedTheme(){
    let savedTheme = localStorage.getItem("aiWriterTheme") || "dark";

    if(savedTheme === "light"){
        document.body.classList.add("light-theme");
    }else{
        document.body.classList.remove("light-theme");
    }

    updateThemeButton();
}

function toggleTheme(){
    let isLight = document.body.classList.toggle("light-theme");

    if(isLight){
        localStorage.setItem("aiWriterTheme", "light");
    }else{
        localStorage.setItem("aiWriterTheme", "dark");
    }

    updateThemeButton();
}

function updateThemeButton(){
    let btn = document.getElementById("themeToggle");

    if(!btn){
        return;
    }

    if(document.body.classList.contains("light-theme")){
        btn.innerText = "🌙 Dark Mode";
    }else{
        btn.innerText = "☀️ Light Mode";
    }
}

function downloadText(elementId, fileName){
    let element = document.getElementById(elementId);
    let text = "";

    if(element){
        text = element.innerText.trim();
    }

    if(text === ""){
        alert("Please generate result first");
        return;
    }

    let blob = new Blob([text], {
        type: "text/plain;charset=utf-8"
    });

    let url = URL.createObjectURL(blob);

    let a = document.createElement("a");
    a.href = url;
    a.download = fileName;

    document.body.appendChild(a);
    a.click();

    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function downloadCurrentResult(){
    let topicSection = document.getElementById("topicSection");
    let improveSection = document.getElementById("improveSection");

    if(topicSection && topicSection.style.display === "block"){
        downloadText("topicOutput", "ai-topic-description.txt");
        return;
    }

    if(improveSection && improveSection.style.display === "block"){
        downloadText("textOutput", "ai-writing-result.txt");
        return;
    }

    let topicOutput = document.getElementById("topicOutput");
    let textOutput = document.getElementById("textOutput");

    let topicText = topicOutput ? topicOutput.innerText.trim() : "";
    let writingText = textOutput ? textOutput.innerText.trim() : "";

    if(writingText !== ""){
        downloadText("textOutput", "ai-writing-result.txt");
    }else if(topicText !== ""){
        downloadText("topicOutput", "ai-topic-description.txt");
    }else{
        alert("Please generate result first");
    }
}
function showTopic(){

document.getElementById("topicSection").style.display="block"
document.getElementById("improveSection").style.display="none"

}

function showImprove(){

document.getElementById("improveSection").style.display="block"
document.getElementById("topicSection").style.display="none"

}


function logoutUser(){
window.location.href="/logout"
}



/* ---------------- LIVE WORD COUNT ---------------- */

function updateWordCount(){

let text = document.getElementById("userText").value

let words = text.trim().split(/\s+/).filter(Boolean).length
let chars = text.length

document.getElementById("wordCount").innerText = words
document.getElementById("charCount").innerText = chars

}



/* ---------------- GENERATE TEXT ---------------- */

async function generateText(){

let text = document.getElementById("userText").value

document.getElementById("loaderText").style.display="block"
document.getElementById("textOutput").innerText=""

let res = await fetch("/generate",{
method:"POST",
headers:{'Content-Type':'application/json'},
body:JSON.stringify({text:text})
})

let data = await res.json()

document.getElementById("loaderText").style.display="none"

document.getElementById("textOutput").innerText = data.result

checkProfessionalAuto()
checkPlagiarism()

}



/* ---------------- CORRECT TEXT ---------------- */

async function correctText(){

let text = document.getElementById("userText").value

document.getElementById("loaderText").style.display="block"
document.getElementById("textOutput").innerText=""

let res = await fetch("/correct",{
method:"POST",
headers:{'Content-Type':'application/json'},
body:JSON.stringify({text:text})
})

let data = await res.json()

document.getElementById("loaderText").style.display="none"

document.getElementById("textOutput").innerText = data.result

checkProfessionalAuto()

}



/* ---------------- ENHANCE TEXT ---------------- */

async function enhanceText(){

let text = document.getElementById("userText").value

document.getElementById("loaderText").style.display="block"
document.getElementById("textOutput").innerText=""

let res = await fetch("/enhance",{
method:"POST",
headers:{'Content-Type':'application/json'},
body:JSON.stringify({text:text})
})

let data = await res.json()

document.getElementById("loaderText").style.display="none"

document.getElementById("textOutput").innerText = data.result

checkProfessionalAuto()
checkPlagiarism()

}



/* ---------------- TOPIC GENERATOR ---------------- */

async function generateTopic(){

let topic = document.getElementById("topicInput").value
let length = document.getElementById("lengthSelect").value

document.getElementById("loaderTopic").style.display="block"
document.getElementById("topicOutput").innerText=""

let res = await fetch("/topic",{
method:"POST",
headers:{'Content-Type':'application/json'},
body:JSON.stringify({topic:topic,length:length})
})

let data = await res.json()

document.getElementById("loaderTopic").style.display="none"

document.getElementById("topicOutput").innerText = data.result

}



/* ---------------- GOOGLE LOGIN HANDLER ---------------- */

function handleCredentialResponse(response){

fetch("/google-login",{
method:"POST",
headers:{
"Content-Type":"application/json"
},
body:JSON.stringify({
token:response.credential
})
})
.then(res=>res.json())
.then(data=>{

if(data.status==="success"){

window.location.href="/index"

}else{

alert("Google login failed")

}

})
.catch(error=>{
console.error("Google login error:",error)
})

}



/* ---------------- WORD COUNT BUTTON ---------------- */

async function wordCount(){

let text = document.getElementById("userText").value

let res = await fetch("/wordcount",{
method:"POST",
headers:{'Content-Type':'application/json'},
body:JSON.stringify({text:text})
})

let data = await res.json()

document.getElementById("textOutput").innerText =
"Words: " + data.words + " | Characters: " + data.characters

}



/* ---------------- PROFESSIONALISM BUTTON ---------------- */

async function checkProfessional(){

let text = document.getElementById("userText").value

document.getElementById("loaderText").style.display="block"

let res = await fetch("/professional",{
method:"POST",
headers:{'Content-Type':'application/json'},
body:JSON.stringify({text:text})
})

let data = await res.json()

document.getElementById("loaderText").style.display="none"

document.getElementById("textOutput").innerText = data.result

}



/* ---------------- AUTO PROFESSIONAL SCORE ---------------- */

async function checkProfessionalAuto(){

let text = document.getElementById("textOutput").innerText

if(text.length < 20){
return
}

let res = await fetch("/professional",{
method:"POST",
headers:{'Content-Type':'application/json'},
body:JSON.stringify({text:text})
})

let data = await res.json()

let score = data.result.match(/\d+/)

if(score){
document.getElementById("professionalScore").innerText = score[0] + "/10"
}else{
document.getElementById("professionalScore").innerText = "Analyzing"
}

}



/* ---------------- PLAGIARISM CHECK ---------------- */

async function checkPlagiarism(){

let text = document.getElementById("userText").value

if(text.trim()===""){
alert("Please enter text first")
return
}

document.getElementById("loaderText").style.display="block"

let res = await fetch("/plagiarism",{
method:"POST",
headers:{'Content-Type':'application/json'},
body:JSON.stringify({text:text})
})

let data = await res.json()

document.getElementById("loaderText").style.display="none"

document.getElementById("plagiarismResult").innerText = data.result

}
/* ---------------- REGENERATE WITH FEEDBACK ---------------- */

async function regenerateText(){

let original = document.getElementById("textOutput").innerText
let feedback = document.getElementById("userFeedback").value

if(original.trim()===""){
alert("Generate text first")
return
}

let res = await fetch("/regenerate",{
method:"POST",
headers:{'Content-Type':'application/json'},
body:JSON.stringify({
original:original,
feedback:feedback
})
})

let data = await res.json()

document.getElementById("textOutput").innerText = data.result

}async function regenerateTopic(){

let original = document.getElementById("topicOutput").innerText
let feedback = document.getElementById("topicFeedback").value

let res = await fetch("/regenerate",{
method:"POST",
headers:{'Content-Type':'application/json'},
body:JSON.stringify({
original: original,
feedback: feedback
})
})

let data = await res.json()

document.getElementById("topicOutput").innerText = data.result

}
