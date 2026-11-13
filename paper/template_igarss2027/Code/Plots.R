library(StatOrdPattHxC)
library(ggplot2)
library(ggthemes)

set.seed(1234567890, kind="Mersenne-Twister")
x <- rnorm(1000) # white noise
y <- mov.av(x, order=101) # smoothed with moving averages
OP1 <- OPprob(x, emb=4)
OP2 <- OPprob(y, emb=4)

H1 <- HShannon(OP1)
H2 <- HShannon(OP2)

C1 <- StatComplexity(OP1)
C2 <- StatComplexity(OP2)

s1 <- sigma2q(x, emb=4)
s2 <- sigma2q(y, emb=4)

sl1 <- qnorm(.95)*sqrt(v1)/sqrt(1000-4)
sl2 <- qnorm(.95)*sqrt(v2)/sqrt(900-4)

HCPoints <- data.frame(H=c(H1,H2),
                       C=c(C1,C2),
                       STD=c(s1,s2),
                       SemiLength=c(sl1,sl2),
                       Series=as.factor(c("White Noise", "Moving Average")))


data("LinfLsup")

D<-4
ggplot(subset(LinfLsup, Side=="Lower" & Dimension==as.character(D)), 
       aes(x=H, y=C)) +
  geom_line(col="gray", linewidth=1.3) +
  geom_line(data=subset(LinfLsup, Side=="Upper" & Dimension==as.character(D)), 
            aes(x=H, y=C),
            col="gray", linewidth=1.3) +
  xlab(expression(italic(H))) +
  ylab(expression(italic(C))) +
  geom_point(data=HCPoints, aes(x=H, y=C, col=Series), size=4) +
  geom_errorbarh(data=HCPoints, 
                 aes(xmin=H-SemiLength, 
                     xmax=H+SemiLength, 
                     group=Series, 
                     col=Series),
                 height=.005, linewidth=1.5) +
  geom_point(aes(x=1, y=0), size=3) +
  coord_cartesian(xlim=c(0.9, 1), ylim=c(0, 0.1)) +
  theme_tufte() +
  theme(legend.position = "top",
        text = element_text(size = 16))

ggsave(file="../Figures/PDF/SinglePlot.pdf")

