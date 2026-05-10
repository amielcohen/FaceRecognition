import { useEffect, useState } from "react";

function App() {
  const [status, setStatus] = useState("loading...");

  useEffect(() => {
    fetch("http://127.0.0.1:8000/status")
      .then((res) => res.json())
      .then((data) => setStatus(data.status))
      .catch((err) => {
        console.error(err);
        setStatus("error connecting");
      });
  }, []);

  return (
    <div style={{ padding: "20px" }}>
      <h1>Face Recognition System</h1>
      <h2>Status: {status}</h2>
    </div>
  );
}

export default App;