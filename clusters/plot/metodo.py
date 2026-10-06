import matplotlib.pyplot as plt
from sklearn.cluster import KMeans


def metodo_do_cotovelo(X, k_max=10, random_state=42):
    """
    Aplica o método do cotovelo para ajudar a escolher o número ideal de clusters.

    Parâmetros:
        X: array-like (n_amostras, n_features) com os dados.
        k_max: maior número de clusters a testar (padrão: 10).
        random_state: semente para reprodutibilidade.

    Retorna:
        Lista com a inércia (WCSS) para cada k de 1 até k_max.
    """
    inercias = []
    ks = range(1, k_max + 1)

    for k in ks:
        kmeans = KMeans(n_clusters=k, init="k-means++", n_init=10, random_state=random_state)
        kmeans.fit(X)
        inercias.append(kmeans.inertia_)

    plt.figure(figsize=(8, 5))
    plt.plot(ks, inercias, marker="o")
    plt.title("Método do Cotovelo")
    plt.xlabel("Número de clusters (k)")
    plt.ylabel("Inércia (WCSS)")
    plt.xticks(list(ks))
    plt.grid(True, alpha=0.3)
    plt.show()

    return inercias