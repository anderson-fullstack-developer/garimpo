/**
 * Sinalizadores de funcionalidade. O MVP é: alertas -> buscar -> resultados -> aviso no Telegram.
 * O resto continua no código, só escondido (menu, links e rotas respondem 404) até fazer sentido.
 */
export const FEATURES = {
  /** Planos, limites visíveis, cobrança e "Fazer upgrade". */
  billing: false,
  /** Painel de administração (usuários, convites, execuções). */
  admin: true,
  /** Gráfico de histórico de preços. */
  history: false,
  /** Página dedicada do monitor (o liga/desliga já fica na tela de Alertas). */
  monitorPage: false,
  /** Página dedicada de destinos (hoje é uma aba em Configurações). */
  destinationsPage: false,
} as const;
