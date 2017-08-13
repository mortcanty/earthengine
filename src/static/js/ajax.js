function sndReq(url,body) {
  resOb.open('post', url, true);
  resOb.onreadystatechange = handleResponse;
  resOb.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
  resOb.send(body);
 }
function handleResponse() {
  if(resOb.readyState == 4 && resOb.status==200){
    document.getElementById("answer").innerHTML = resOb.responseText;
    document.body.style.cursor='default';
  }
 }
var resOb = null;
try { resOb = new XMLHttpRequest();} 
   catch(e) {
      try {resOb = new ActiveXObject("MSMXL2.XMLHTTP");} 
         catch(e) {
            try {resOb = new ActiveXObject("Microsoft.XMLHTTP");} 
               catch(e) {
               }
         }    
   }            