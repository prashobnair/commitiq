import React, { useState } from 'react';
import axios from 'axios';

function App() {
  const [username, setUsername] = useState('');
  const [analysisData, setAnalysisData] = useState(null);
  const [error, setError] = useState('');

  const fetchData = async () => {
    setError('');
    try {
      const response = await axios.get(`http://localhost:5000/api/github/analyze/${username}`);
      setAnalysisData(response.data);
    } catch (err) {
      if (err.response) {
        setError(err.response.data.error || 'An error occurred.');
      } else {
        setError('Network error or server is down.');
      }
      setAnalysisData(null);
    }
  };

  return (
    <div>
      <h1>CommitIQ</h1>
      <input
        type="text"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        placeholder="Enter GitHub username"
      />
      <button onClick={fetchData}>Analyze</button>

      {error && <p style={{ color: 'red' }}>{error}</p>}

      {analysisData && (
        <div>
          <h2>Analysis for {analysisData.analysis.username}</h2>
          <p>Impact Score: {analysisData.impact_score}</p>
            <div>
              <h3>Aggregated Data</h3>
                <p>Merged PRs: {analysisData.analysis.merged_prs}</p>
                <p>Issues Created: {analysisData.analysis.issues_created}</p>
                <p>Issues Resolved: {analysisData.analysis.issues_resolved}</p>
                <p>Code Reviews: {analysisData.analysis.code_reviews}</p>
                <p>Total commits: {analysisData.analysis.total_commits}</p>
                <p>Project Impact: {analysisData.analysis.project_impact}</p>
            </div>

          <h3>Repository Details</h3>
            {analysisData.analysis.repos.map((repo, index) => (
                <div key={index}>
                    <h4>{repo.name}</h4>
                    <p>URL: <a href={repo.url} target="_blank" rel="noopener noreferrer">{repo.url}</a></p>
                    <p>Stars: {repo.stars}</p>
                    <p>Forks: {repo.forks}</p>
                    <p>Contributors: {repo.num_contributors}</p>
                    <p>Commit Frequency: {repo.commit_frequency}</p>
                    <p>Last Updated: {repo.last_updated}</p>
                    <p>Number of Commits: {repo.num_commits}</p>
                    <p>Individual Project Impact: {repo.impact_score}</p>
                </div>
            ))}
        </div>
      )}
    </div>
  );
}

export default App;