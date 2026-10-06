from sklearn.cluster import KMeans
from rich.console import Console

console = Console()


class KMeansCluster:
  def __init__(self, n_clusters=8, max_iter=300, random_state=42):
    self.n_clusters = n_clusters
    self.max_iter = max_iter
    self.random_state = random_state

  def fit(self, X):
    with console.status(f"[bold green]Treinando KMeans com {self.n_clusters} clusters..."):
      self.kmeans = KMeans(n_clusters=self.n_clusters, max_iter=self.max_iter, random_state=self.random_state)
      self.kmeans.fit(X)
    console.print("[bold green]Treinamento KMeans concluído! :white_check_mark:[/bold green]")

  def predict(self, X):
    with console.status("[bold blue]Prevendo clusters..."):
      predictions = self.kmeans.predict(X)
    console.print("[bold blue]Previsões concluídas! :white_check_mark:[/bold blue]")
    return predictions