from sklearn.preprocessing import StandardScaler

def padronizar(X):
    scaler = StandardScaler()
    X_padronizado = scaler.fit_transform(X)
    return X_padronizado