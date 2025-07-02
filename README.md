# PROGRAMA PARA ANÁLISE DAS VENDAS E ESTOQUE

### Programado para arquivos especificos, mas isso pode ser facilmente ajustado no código!!!
--------------------------------------------------------------------------------------------
Com esse programa, você pode receber análise de suas vendas e prvisão futura em gráficos pandas, os calculos são feitos usando uma função quadrática com uma abordagem bayesiana!

### Como usar!
Para utilizar, ir no destino onde o programa esta (ex:. destino/do/arquivo), USANDO O 'cmd', digite:
```cmd
py app.py
```

As opções são:
```python
'1: Atualizar dados das vendas e gerar previsões!' # Caso ter novos dados na entrada de vendas
'2: Atualizar dados do estoque!' # Caso ter novos dados na entrada de estoque e sempre que atualizar as vendas
'3: Ver previsão de um SKU e conta específicos!' # Escolha um sku que deseja e uma conta, será gerado um gráfico dependendo da escolha (o sku precisa existir na tabela de previsão_futura)
'4: Fazer uma previsão geral por Sku!' # Escolha um sku, essa não depende da tabela de previsões, pois gera o resultado na hora
'5: Fazer previsão do estoque!' # Escolha um sku para prever estoque
'6: Sair do programa!' # Encerrar o programa
```
### OBS:. As previões são pré definidas em 360 dias para o futuro, em breve poderá ter a opção de escolher.

