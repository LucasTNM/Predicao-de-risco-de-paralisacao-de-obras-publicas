# Estados
verificar_engine → solicitar_inicio (se necessário) → aguardar_engine → verificar_servico → iniciar_servico (se necessário) → aguardar_saude → pronto. Qualquer etapa pode encerrar com erro/timeout.
Resultado: engine_iniciado, servico_iniciado, contexto, duração. Evidência do teste inclui igualdade do digest das observações completas; nunca DSN.
