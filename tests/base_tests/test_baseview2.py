import base64
import logging
from unittest import mock

import pytest

from slim import Application
from slim.base.view import BaseView
from slim.tools.test import make_mocked_request, make_mocked_view

pytestmark = [pytest.mark.asyncio]


app = Application(cookies_secret=b'123456', permission=None, log_level=logging.DEBUG)
captcha = 'iVBORw0KGgoAAAANSUhEUgAAArYAAAExCAYAAACJXuERAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAgY0hSTQAAeiYAAICEAAD6AAAAgOgAAHUwAADqYAAAOpgAABdwnLpRPAAAL19JREFUeF7tnU2uJklyXZML0ID6oQQBAltAAwIJDTRpaKgFaKyp5hpzOVxJroHA20At5lN/hWYDlfky67rH9bjXPc4DcsK2MDc7ZhFxMupV8W8+Pj5eX/iBAAQgAAEIQAACEIDA7gTeYssfGLAD7AA7wA6wA+wAO8AO7L4DX3ZvgPq5CdkBdoAdYAfYAXaAHWAHfv0tBBaBRWAH2AF2gB1gB9gBdoAdOGEHEFt+FYNfRWEH2AF2gB1gB9gBduCIHUBsWeQjFvmEv2XSA19L2AF2gB1gB9iBazuA2CK2iC07wA6wA+wAO8AOsANH7ABiyyIfscj8Dffa33DhBz92gB1gB9iBE3YAsUVsEVt2gB1gB9gBdoAdYAeO2AHElkU+YpFP+FsmPfC1hB1gB9gBdoAduLYDX178QAACEIAABCAAAQjcTuDr16+vxJ/bG1104Gd/CUBsF8EmLQQgAAEIQAACEPgZgYTUvs885QexPWWS9AEBCEAAAhCAwPYEENtrI0Rsr/HjaghAAAIQgAAEIGAjgNheQ4nYXuPH1RCAAAQgAAEIQMBGALG9hhKxvcaPqyEAAQhAAAIQgICNAGJ7DSVie40fV0MAAhCAAAQgAAEbAcT2GkrE9ho/roYABCAAAQhAAAI2AojtNZSI7TV+XA0BCEAAAhCAAARsBBDbaygR22v8uBoCEIAABCAAAQjYCCC211Aittf4cTUEIAABCEAAAhCwEUBsr6FEbK/x42oIQAACEIAABCBgI4DYXkOJ2F7jx9UQgAAEIAABCEDARgCxvYYSsb3Gj6shAAEIQAACEICAjQBiew0lYnuNH1dDAAIQgAAEIPBwAk4ZfTjKy+0jtpcRkgACEIAABCAAgScTQGx7po/Y9syCSiAAAQhAAAIQ2JAAYtszNMS2ZxZUAgEIQAACEIDAhgQQ256hIbY9s6ASCEAAAhCAAAQ2JIDY9gwNse2ZBZVAAAIQgAAEILAhAcS2Z2iIbc8sqAQCEIAABCAAgQ0JILY9Q0Nse2ZBJRCAAAQgAAEIbEgAse0ZGmLbMwsqgQAEIAABCEBgQwKIbc/QENueWVAJBCAAAQhAAAIbEkBse4aG2PbMgkogAAEIQAACENiQAGLbMzTEtmcWVAIBCEAAAhCAwIYEENueoSG2PbOgEghAAAIQgAAENiSA2PYMDbHtmQWVQAACEIAABCCwIQHEtmdoiG3PLKgEAhCAwOv//rf/LP0B1X4E/s1//Hcv5c9+nfVU7BTMkVwqASWnmou4zwkgtmwGBCAAgSICiG3RMMylKFL7juFnnoAijiti1IqVs9VcxCG27AAEIACBegKIbf2IpgtEbKfRyRcq4rgiRi1QOVvNRRxiyw5AAAIQqCeA2NaPaLpAxHYanXyhIo4rYtQClbPVXMQhtuwABCAAgXoCiG39iKYLRGyn0ckXKuK4IkYtUDlbzUUcYssOQAACEKgngNjWj2i6QMR2Gp18oSKOK2LUApWz1VzEIbbsAAQgAIF6Aoht/YimC0Rsp9HJFyriuCJGLVA5W81FHGLLDkAAAhCoJ4DY1o9oukDEdhqdfKEijiti1AKVs9VcxCG27AAEIACBegKIbf2IpgtEbKfRyRcq4rgiRi1QOVvNRRxiyw5AAAIQqCeA2NaPaLpAxHYanXyhIo4rYtQClbPVXMQhtuwABCAAgXoCiG39iKYLRGyn0ckXKuK4IkYtUDlbzUUcYssOQAACEKgngNjWj2i6QMR2Gp18oSKOK2LUApWz1VzEIbbsAAQgAIF6Aoht/YimC0Rsp9HJFyriuCJGLVA5W81FHGLLDkAAAhCoJ4DY1o9oukDEdhqdfKEijiti1AKVs9VcxCG27AAEIFBGQHnI7xBThpVyIBAnkLpvU42r/abqe9K5Hx8fr2//fHkSAHqFAARyBNSXQXtcjiAnQ6CTQOqeTdFQ+03V96RzEdsnTZteIVBGQH0ZtMeVYaUcCMQJpO7ZVONqv6n6nnQuYvukadMrBMoIqC+D9rgyrJQDgTiB1D2balztN1Xfk85FbJ80bXqFQBkB9WXQHleGlXIgECeQumdTjav9pup70rmI7ZOmTa8QKCOgvgza48qwUg4E4gRS92yqcbXfVH1POhexfdK06RUCZQTUl0F7XBlWyoFAnEDqnk01rvabqu9J5yK2T5o2vUKgjID6MmiPK8NKORCIE0jds6nG1X5T9T3pXMT2SdOmVwiUEVBfBu1xZVgpBwJxAql7NtW42m+qviedi9g+adr0CoEyAurLoD2uDCvlQCBOIHXPphpX+03V96RzEdsnTZteIVBGQH0ZtMeVYaUcCMQJpO7ZVONqv6n6nnQuYvukadMrBMoIqC+D9rgyrJQDgTiB1D2balztN1Xfk85FbJ80bXqFQBkB9WXQHleGlXIgECeQumdTjav9pup70rmI7ZOmTa8QKCOgvgza48qwUg4E4gRS92yqcbXfVH1POvcosf3jn14v558nLYKT2zvXCT//8x/+4aX8UR9oxH19fcvghD2hBwicQsD5jDqFidqHyk7NR9w8AcT2JzI8j3W/KxHb72emSO07Rn2gEYfY7vdkoOInEXA+o57E7d2ryu5pXBL9IraI7a97h9gituqD2RmXeOhxJgQg8DkB7u35zVDZzZ/AlSoBxBaxRWx/cLfwxfb7L6zqw1uNUx9UxEEAAusJqPetEre+2q4TFCbvGH7WE0BsEVvEFrGV/zGa+vBW49Y/4jgBAhBQCaj3rRKnnnlKnMIEsb1n2ogtYovYIraI7T3PW06BQDUBVc6UuOpGFxSnMEFsF4D/JCVii9gitogtYnvP85ZTIFBNQJUzJa660QXFKUwQ2wXgEduxf0nqnhF0nMK/PPb9HPgdW37HtuPupAoI3ENAlTMl7p6Ke05RmCC298yLL7Z8seWLLV9s+WJ7z/OWUyBQTUCVMyWuutEFxSlMENsF4PliyxfbH60VX2z5Yqs+mJ1x9zzmOAUCEFAIcG8rlD6PUdnNn8CVKgG+2PLFli+2fLHli636xCQOAgcTUOVMiTsY06etKUz4YnvPViC2iC1ii9gitvc8bzkFAtUEVDlT4qobXVCcwgSxXQCeX0XgVxH4VQT9xuJfHuNfHtO3hUgI7E9AlTMlbn8aYx0oTBDbMaaz0Xyx5YstX2z5YssX29knKNdB4CACqpwpcQdhkVpRmCC2EsrLQYjt4WLb/i+FqQ+D5rjLd+Fkgn/6x19e/Pktg0mUXDZA4O/+8F9eyp+BlLbQv//D69X8R2009bxT63tS3L/8h39+Of/Abp6nyg6xRWxfI/KrLpYal3qAO89Ve3XHIbXfi72bMfm+J6BI7Tsm8dMste/a1B/n82kkl1rfk+KcUvvO9aSfFDvEFrFFbL9e+13S1IMKsUVsE7uH2M5/FVbnNSKjzli1vifFpeTsBMYpdogtYovYIrbH/ErDCS+D9h4QW8S2fUed9aXkzNlDKleKHWKL2CK2iC1im3ryb3guYovYbri20yWn5Gy64KILU+wQW8QWsUVsEduil0F7KYgtYtu+o876UnLm7CGVK8UOsUVsEVvEFrFNPfk3PBexRWw3XNvpklNyNl1w0YUpdogtYovYIraIbdHLoL0UxBaxbd9RZ30pOXP2kMqVYofYIraILWKL2Kae/Buei9githuu7XTJKTmbLrjowhQ7xBaxRWwRW8S26GXQXgpii9i276izvpScOXtI5UqxQ2wRW8QWsUVsU0/+Dc9FbBHbDdd2uuSUnE0XXHRhih1ii9gitogtYlv0MmgvBbFFbNt31FlfSs6cPaRypdghtogtYovYIrapJ/+G5yK2iO2GaztdckrOpgsuujDFDrFFbBFbxBaxLXoZtJeC2CK27TvqrC8lZ84eUrlS7BBbxBaxRWwR29STf8NzEVvEdsO1nS45JWfTBRddmGKH2G4qtn/8Sd0z/1vRvUApIoF/+sdfjhHS1l7EURB2gcDf/2FeFJ9+7QXsj7/0q/hBIyVnJwwoxQ6xRWx//WLLz34EWmXwpLr224r9Kn66nF7pf79p91SM2K6fBWJrYDzzpfJn1xhKWpbiSb0ug7h54pMEsrWXzVdki/KviN3Tr91iwKVFIrbrB4PYGhg/Sfae1KthNY5M0SqDJ9V15OKUNfV0Ob3Sf9kotyoHsV0/LsTWwPhJsvekXg2rcWSKkwSytZcjF6esqSti9/Rry0a5VTmI7fpxIbYGxk+SvSf1aliNI1O0yuBJdR25OGVNPV1Or/RfNsqtykFs148LsTUwfpLsPalXw2ocmeIkgWzt5cjFKWvqitg9/dqyUW5VDmK7flyIrYHxk2TvSb0aVuPIFK0yeFJdRy5OWVNPl9Mr/ZeNcqtyENv140JsDYyfJHtP6tWwGkemOEkgW3s5cnHKmroidk+/tmyUW5WD2K4fF2JrYPwk2XtSr4bVODJFqwyeVNeRi1PW1NPl9Er/ZaPcqhzEdv24EFsD4yfJ3pN6NazGkSlOEsjWXo5cnLKmrojd068tG+VW5SC268eF2BoYP0n2ntSrYTWOTNEqgyfVdeTilDX1dDm90n/ZKLcqB7FdPy7E1sD4SbL3pF4Nq3FkipMEsrWXIxenrKkrYvf0a8tGuVU5iO36cSG2BsZPkr0n9WpYjSNTtMrgSXUduThlTT1dTq/0XzbKrcpBbNePC7E1MD5B9k7owTBKUggEnAIpHLdFiJPJOxc/6wlcEbtvr1VlRY1zd+/s9Z2Ln3kC6g6k5Gy+s54rU+w+Pj5e3/750oNlrJITpPCEHsamRvQsAafEzdbQdp2TCWJ7z3SdsqfKihrnJuDsFbG9Nh11B1Jydq27jqtT7BDbP71eP5LJxGogtgnqe57plLg9CXxftZMJYnvPVjhlT5UVNc5NwNkrYnttOuoOpOTsWncdV6fYIbaIbccdQBXDBJwSN3x46QVOJojtPUN2yp4qK2qcm4CzV8T22nTUHUjJ2bXuOq5OsUNsEduOO4Aqhgk4JW748NILnEwQ23uG7JQ9VVbUODcBZ6+I7bXpqDuQkrNr3XVcnWKH2CK2HXcAVQwTcErc8OGlFziZILb3DNkpe6qsqHFuAs5eEdtr01F3ICVn17rruDrFDrFFbDvuAKoYJuCUuOHDSy9wMkFs7xmyU/ZUWVHj3AScvSK216aj7kBKzq5113F1ih1ii9h23AFUMUzAKXHDh5de4GSC2N4zZKfsqbKixrkJOHtFbK9NR92BlJxd667j6hQ7xBax7bgDqGKYgFPihg8vvcDJBLG9Z8hO2VNlRY1zE3D2ithem466Ayk5u9Zdx9UpdogtYttxB1DFMAGnxA0fXnqBkwlie8+QnbKnyooa5ybg7BWxvTYddQdScnatu46rU+wQW8S24w6gimECTokbPrz0AicTxPaeITtlT5UVNc5NwNkrYnttOuoOpOTsWncdV6fYIbaIbccdQBXDBJwSN3x46QVOJojtPUN2yp4qK2qcm4CzV8T22nTUHUjJ2bXuOq5OsUNsEduOO4Aqhgk4JW748NILnEwQ23uG7JQ9VVbUODcBZ6+I7bXpqDuQkrNr3XVcnWKH2CK2HXcAVQwTcErc8OGlFziZILb3DNkpe6qsqHFuAs5eEdtr01F3ICVn17rruDrFDrG9SWz/+JNzZv63jrXtquJ//ae/fSl/uqqer8YpcfNVdF2pvqyc7BDgz3fALXHKbLu2cb4aN7v5Sva7UtmTd4z6k5Iztb7muBQ7xBaxbb4vhmpTpPYdc8qPU85OYaK+1JzsEFvE1n3/ILbzRNVngHpCSs7U+prjUuwQW8S2+b4Yqg2x/eU1K2xDoIuD1ZfaLKcfXVeMJFaaW86U2caaNR/sZmcurzqdsid8sb1nhIitgfPMP9L/2TWGkv6aork2Z5/JXIgtYqu+1BDb9XeqW86U2a7v6p4T3OzuqbrjFGVPENt7ZoXYGjg3y2NzbQb0FSkQW8RWfakhtutvWbecKbNd39U9J7jZ3VN1xynKniC298wKsTVwbpbH5toM6CtSILaIrfpSQ2zX37JuOVNmu76re05ws7un6o5TlD1BbO+ZFWJr4Nwsj821GdBXpEBsEVv1pYbYrr9l3XKmzHZ9V/ec4GZ3T9Udpyh7gtjeMyvE1sC5WR6bazOgr0iB2CK26ksNsV1/y7rlTJnt+q7uOcHN7p6qO05R9gSxvWdWiK2Bc7M8NtdmQF+RArFFbNWXGmK7/pZ1y5ky2/Vd3XOCm909VXecouwJYnvPrBBbA+dmeWyuzYC+IgVii9iqLzXEdv0t65YzZbbru7rnBDe7e6ruOEXZE8T2nlkhtgbOzfLYXJsBfUUKxBaxVV9qiO36W9YtZ8ps13d1zwludvdU3XGKsieI7T2zQmwNnJvlsbk2A/qKFIgtYqu+1BDb9besW86U2a7v6p4T3OzuqbrjFGVPENt7ZoXYGjg3y2NzbQb0FSkQW8RWfakhtutvWbecKbNd39U9J7jZ3VN1xynKniC298wKsTVwbpbH5toM6CtSILaIrfpSQ2zX37JuOVNmu76re05ws7un6o5TlD1BbO+ZFWJr4JyQR/eZ7nwGrKQoJeCUs9IWl5XlZPfOpb5MnXFuOM7a3rmQs/kJwW6enbrH6gkpOVPra45Lsfv4+Hh9++dLM6if1ZaQQveZ7ny7zpK6f5+AU85+/7SzIpzsENuvn4o9cjZ/z8Bunh1iO8/OfSViayCakEL3me58BqykKCXglLPSFpeV5WSH2CK27kVFbOeJIrbz7NxXIrYGogkpdJ/pzmfASopSAk45K21xWVlOdogtYuteVMR2nihiO8/OfSViayCakEL3me58BqykKCXglLPSFpeV5WSH2CK27kVFbOeJIrbz7NxXIrYGogkpdJ/pzmfASopSAk45K21xWVlOdogtYuteVMR2nihiO8/OfSViayCakEL3me58BqykKCXglLPSFpeV5WSH2CK27kVFbOeJIrbz7NxXIrYGogkpdJ/pzmfASopSAk45K21xWVlOdogtYuteVMR2nihiO8/OfSViayCakEL3me58BqykKCXglLPSFpeV5WSH2CK27kVFbOeJIrbz7NxXIrYGogkpdJ/pzmfASopSAk45K21xWVlOdogtYuteVMR2nihiO8/OfSViayCakEL3me58BqykKCXglLPSFpeV5WSH2CK27kVFbOeJIrbz7NxXIrYGogkpdJ/pzmfASopSAk45K21xWVlOdogtYuteVMR2nihiO8/OfSViayCakEL3me58BqykKCXglLPSFpeV5WSH2CK27kVFbOeJIrbz7NxXIrYGogkpdJ/pzmfASopSAk45K21xWVlOdogtYuteVMR2nihiO8/OfSViayDqlkJnPrU955nvXPycS8ApZ+6XQTt1J7t3rsSPOrNUHHI2vxWw+56dusfz1D+/MiVn7j4S+VLsPj4+Xt/++ZIA4DjTLYXOfGp/zjMRW5X6nnFOOUu9NFLknewQW77YuvcYsUVs3TuVyIfYGqi7pdCZT23PeSZiq1LfM84pZ4jtL68rPBMbpM4sFYeczW8F7BDb+e3puRKxNczCLYXOfGp7zjMRW5X6nnFXROzba1X52ZPU91U72fHFli+27vsCsUVs3TuVyIfYGqi7pdCZT23PeSZiq1LfM84pZ4gtX2zVHVDjkLP55wrsENv57em5ErE1zMIthc58anvOMxFblfqecYjt/Nyc7Phiyxfb+U38/ErEFrF171QiH2JroO6WQmc+tT3nmYitSn3POKecqV/h9iTFryKo83XGIWfzdwvsENv57em5ErE1zMIthc58anvOMxFblfqecYjt/Nyc7Phiyxfb+U3ki63KTv1Ll5pPjUvJmVpfc1yKHf+5rz//t17dMvlZPnX53LWo5xK3HwGnnKVeGinqTnaILWLr3mO+2PLF1r1TiXyIrYG6Wwqd+dT2nGfyxValvmecU84QW/7lMXUH1DjkbP65AjvEdn57eq5EbA2zcEuhM5/anvNMxFalvmccYjs/Nyc7vtjyxXZ+E/lVBJWd+hcqNZ8al5Iztb7muBQ7fhWBX0Vovi+o7ScEnHKWemmkBuxkh9gitu495ostX2zdO5XIh9gaqLu/djrzqe05z+SLrUp9zzinnCG2/CqCugNqHHI2/1yBHWI7vz09VyK2hlm4pdCZT23PeSZiq1LfMw6xnZ+bkx1fbPliO7+J/CqCyk79C5WaT41LyZlaX3Ncih2/inDxVxHUm80dd4oAu7ko+ZofBCO1OeVMPVfhu0OMk11KbNWZpeLcXx2de5Viop6bYqfW54xT5+o8cyRXSs5GamyNTbFDbBHbX/9zZ6kf9aHmjEv16j7XKWdqbc45JHM52SG293x1dO6Luu+pOMT2+38KkJpFSs5S/TrPTbFDbBFbxNZ5J9+YyylnatlOuUjmcrJDbBFb9f5R4xBbxFbdleY4xNYwHfc/nlfypV7OSm0jMQb8UykS/KYKLbzIKWdqe4l5rTjTyQ6xRWzV+0eNQ2wRW3VXmuMQW8N0RkTOFbvipavkdNX/r3kM+KdSKL26Y6YKLbzIKWdqe+5ZpPI52SG2iK16/6hxiC1iq+5Kcxxia5iOW/aUfKkXs1LbSIwB/1SKBL+pQgsvcsqZ2l5iXivOdLJDbBFb9f5R4xBbxFbdleY4xNYwnRGRc8WueOkqOV3188XWsHihFE45U1tQdnOHGCc7xBaxVe8fNQ6xRWzVXWmOQ2wN03HLnpIv9RJXahuJMeCfSpHgN1Vo4UVOOVPbS8xrxZlOdogtYqveP2ocYovYqrvSHIfYGqYzInKu2BUvXSWnq36+2BoWL5TCKWdqC8pu7hDjZIfYIrbq/aPGIbaIrborzXGIrWE6btlT8qVe4kptIzEG/FMpEvymCi28yClnanuJea0408kOsUVs1ftHjUNsEVt1V5rjEFvDdEZEzhW74qWr5HTVzxdbw+KFUjjlTG1B2c0dYpzsEFvEVr1/1DjEFrFVd6U5DrE1TMcte0q+1EtcqW0kxoB/KkWC31ShhRc55UxtLzGvFWc62SG2iK16/6hxiC1iq+5Kcxxia5jOiMi5Yle8dJWcrvr5YmtYvFAKp5ypLSi7uUOMkx1ii9iq948ah9gituquNMchtobpuGVPyZd6iSu1jcQY8E+lSPCbKrTwIqecqe0l5rXiTCc7xBaxVe8fNQ6xRWzVXWmOQ2wN0xkROSXWUNKyFEr9IzEr5IGc3z+cnUyccrZsUUsTO9m9cznnmsrlHpVbzpz1pRir57rZqec6Gau5mmt795CSM5Vfc1yK3cfHx+vbP1+aQf2sthGRU2KbOSj1j8SoDxfi1srqCF+nnDXv+oranOwQ23u+2Dr3YOQ+S8Qitnyxde57KhdiayA/InJKrKGkZSmU+kdiEg9vzrwmyU45W7aopYmd7BBbxNb9LENsEdvSR+dQWYjtEK7Pg0dETok1lLQshVL/SIz7wUy+a9Kq8HPK2bJFLU3sZIfYIrbK/ToSg9gitqWPzqGyENshXIjtiLQqsSMPXWLXS6vC2ClnhttvqxROdogtYqvcryMxiC1iu9UD9QfFIraGKSoCNxJjKGlZipE+lNiRhy6xiO2yxb4pMWK7XhzccuZcjfZnmJud2q+TsZqrubZ3Dyk5U/k1x6XY8S+P/en1+pH4NS+MIqsjMerDhbgOqX3PwSlnzbu+ojYnO77Y8sXW/VxEbNf/xUt9rqTkTK2vOS7FDrFFbH8Ve/eDmXzrBdgpZ80PxxW1Odkhtoit+3mH2CK2K557d+dEbA3ER75QKrGGkpalUOofiXE/mMmH2C5bfkNixHa9OLjlzDD2v6Zofz652an9OhmruZpr41cR1Cl+HofYXuP369UjIqfEGkpalkKpfyRGfbgQt15YVcZOOVu2qKWJnez4YssXW/WeVeMQ2/V/8VIfTSk5U+trjkux41cR+FUEfhXhz7+vqr5wmuKcctb8cFxRm5MdYovYup8LiC1iu+K5d3dOxNZAfOQLpRJrKGlZCqX+kRj3g5l862XZKWfLFrU0sZMdYovYup93iC1iW/roHCoLsR3C9XnwiMgpsYaSlqVQ6h+JcT+YyYfYLlt+Q2LEdr04uOXMMPa/pmh/PrnZqf06Gau5mmt795CSM5Vfc1yKHb+KwK8i8KsI/CpC87NxSW2ILWKrClUiDrFdv5/qgyUlZ2p9zXEpdojtpmKrLvPIV1slVj33hLjEC23kTKecjZzrjE3tiZPdO9cJP865vnMl5Eydg7s29Vw1zl2fc7ZqD+qZar5UXErOUv06z02xQ2wR26H/moRz6dtzqQ/mVJxTzlI9pHbAyQ6x/fzXbhJypu6Tuzb1XDXOXZ/z/lZ7UM9U86XiUnKW6td5boodYovYIrY/uJPVB3MqzilnqR6cD9GRXE52iC1iO7J7Sixiq1C6JyYlZ/d0t/aUFDvEFrFFbBHb2H/ubO1j9cfZEdvv2bj/cpOQM3Wf3LWp56px7vqcs1V7UM9U86XiUnKW6td5boodYovYIraILWL759+TvSK7zpdBKpcqImpcQs5Udu7a1HPVOHd96syUOLUHJdc7pv0nJWftXJT6UuwQW8QWsUVsEVvE1r4DCTlTXrbvGHdt6rlqnLs+VTKVOLUHJRdiq9LcMw6xNcxN+bf6R2IMJcVTjPSrxMYburEA9cGcirvyhfHba1M93DjO3xzlZMfv2PI7tu49RmzdROfzpeRsvuKeK1Ps+GLLF1u+2PLF1v61ThXl1CMYsf2evDozNS4hZ+o+uWtTz1Xj3PWpM1Pi1B6UXHyxVWnuGYfYGuamfHEciTGUFE8x0q8SG2/oxgLUB3MqzilnqR5uHCdfbH8HtnsHEnKm7pO7NvVcNc5dn3O2ag/qmWq+VFxKzlL9Os9NseOLLV9s+WLLF1u+2PI7tvYdSMiZ+lJ216aeq8a561MlU4lTe1By8cVWpblnHGJrmJvyxXEkxlBSPMVIv0psvKEbC1AfzKk4vtjOL4OTHb9jy+/Yzm/i51citm6i8/lScjZfcc+VKXZ8seWLLV9s+WJr/1qnyn7qEYzYfk9enZkal5AzdZ/ctannqnHu+tSZKXFqD0ouvtiqNPeMQ2wNc1O+OI7EGEqKpxjpV4mNN3RjAeqDORXnlLNUDzeO8zdHOdnxxZYvtu49RmzdROfzpeRsvuKeK1Ps+GLLF1u+2PLFli+2/I6tfQcScqa+0t21qeeqce76nH9xVXtQz1TzpeJScpbq13luih1ii9gitoitXWraX2p8seVXEZzy6JSBdy5nbe9c6v2oxKm9Krn4VQSV5p5xiK1hbso/Sh+JMZQUTzHSrzM23vgDCnDKmRuX+lJzxzmZvHO561PynTILtQ+nxCl8R2Kcta3IpTJ2xo3wS8Q6e33ncsuZks/dgzuf0sOKGLUPvtjyxXboi60qv+oCEjdPwClx81V8fmXihfY+08kEsf38d2fV2ao75RQ+tTY1zlnbilwqY2ecyi4V5+wVsf2c5gppVXKqs0VsEVvEVr1byuKcEuduLfVSczJBbBHbFTLqzOm+b5V8qXtbPVfpYSRGES53zEh9iVh3v2o+tVfEFrFFbNW7pSzOKXHu1tSXkDvOyQSxRWydEroil/u+VfK571l3PqWHkRhVupxxI/UlYp29juRSe0VsEVvEVr1byuKcEuduzf2yUvM5mSC2iO0KGXXmdN+3Sj71XkzFKT2MxIyIlyt2pL5ErKvP0Txqr4gtYovYqndLWZxT4tytpV5qTiaILWLrlNAVudz3rZIvdW+r5yo9jMSMypcjfqS+RKyjx5kcaq+ILWKL2Kp3S1mcU+LcrakvIXeckwlii9iukFFnTvd9q+Rz37PufEoPIzEzAnb1mpH6ErFX+5u9Xu0VsUVsEVv1bimLc0qcuzX3y0rN52SC2CK2Tgldkct93yr51HsxFaf0MBIzK2FXrhupLxF7pbcr16q9IraILWKr3i1lcU6Jc7eWeqk5mSC2iO0KGXXmdN+3Sr7Uva2eq/QwEnNFxGavHakvETvb19Xr1F4RW8QWsVXvlrI4p8S5W1NfQu44JxPEFrF1SuiKXO77Vsnnvmfd+ZQeRmKuytjM9SP1JWJnenJco/aK2CK2iK16t5TFOSXO3Zr7ZaXmczJBbBHbFTLqzOm+b5V86r2YilN6GIlxCNlojpH6ErGj/bji1V4RW8QWsVXvlrI4p8S5W0u91JxMEFvE1imhK3K571slX+reVs9VehiJcUnZSJ6R+hKxI704Y9VeEVvEFrFV75ayOKfEuVtTX0LuOCcTxBaxXSGjzpzu+1bJ575n3fmUHkZinGKm5hqpLxGr9uGOU3tFbBFbxFa9W8rinBLnbs39slLzOZkgtoitU0JX5HLft0o+9V5MxSk9jMS45UzJN1JfIlbpYUWM2itie7jYqovwx59wmPnf1HOJmyfgljjy/fL6loE6ndRL/IRzVwjfU3KeMH/1HlPjUkxWiNxTcqqzVeMQW8T2112ZkdefXaMuIHHzBBDR70XUzUSdTuplesK5T5HQFX2eMH/1HlPjUkyeIqEr+lRnq8YhtogtYqveLWVxbokjH19sE1KwQviekjMxL/eZ7sequz413wrhe0pO9w4gtogtYuu+q27Kh4jyxVZ96TbHPUVCV/TZPFe1NvfjUj3XHfcUCV3Rp3sHEFvEFrF131U35UNsEVv3yzmRb4XwPSVnYl7uM92PS3d9ar4VwveUnO4dQGwRW8TWfVfdlA+xRWzVl25z3FMkdEWfzXNVa3M/LtVz3XFPkdAVfbp3ALFFbBFb9111Uz7EFrF1v5wT+VYI31NyJublPtP9uHTXp+ZbIXxPyeneAcQWsUVs3XfVTfkQW8RWfek2xz1FQlf02TxXtTb341I91x33FAld0ad7BxBbxBaxdd9VN+VDbBFb98s5kW+F8D0lZ2Je7jPdj0t3fWq+FcL3lJzuHUBsEVvE1n1X3ZQPsUVs1Zduc9xTJHRFn81zVWtzPy7Vc91xT5HQFX26dwCxRWwRW/dddVM+xBaxdb+cE/lWCN9Tcibm5T7T/bh016fmWyF8T8np3gHEFrFFbN131U35EFvEVn3pNsc9RUJX9Nk8V7U29+NSPdcd9xQJXdGnewcQW8QWsXXfVTflQ2wRW/fLOZFvhfA9JWdiXu4z3Y9Ld31qvhXC95Sc7h1AbBFbxNZ9V92UD7FFbNWXbnPcUyR0RZ/Nc1Vrcz8u1XPdcU+R0BV9unfgKLF1wyEfBJoJILbfi637ZaXma94TtTa11+a4FfKo5FSZKLlGYtRznXHqPqlxztp2yLVCDFtzqjvgjkNs3UTJB4GbCCC2iK1z1XaQgt+rcUQKnbG/V9e//u/OM9+51HOdcc6de+dy1rZDrlYJXVGXe1fUfIitSoo4CJQRQGwRW+dK7iAFv1ejWxzVfL9XF2L7401V2Z0St0IgW3M6n08juRDbEVrEQqCIAGKL2DrX8QRxUEXUHaeyS52r1qfEOXeOL7b//GqVUkdd7l1R8yG2KiniIFBGALFFbJ0rqUhNe4xbHNV8Khc1nxqnnuuMc+4cYovYuvfpnQ+xXUGVnBC4gQBii9g618wpP6lcqhC649R+U+eq9Slxzp1DbBFb9z4htiuIkhMCNxFAbBFb56opUtMe4xZHNZ/KRc2nxqnnOuOcO4fYIrbufUJsVxAlJwRuIoDYIrbOVXPKTyqXKoTuOLXf1LlqfUqcc+cQW8TWvU+I7Qqi5ITATQQQW8TWuWqK1LTHuMVRzadyUfOpceq5zjjnziG2iK17nxDbFUTJCYGbCCC2iK1z1Zzyk8qlCqE7Tu03da5anxLn3DnEFrF17xNiu4IoOSFwEwHEFrF1rpoiNe0xbnFU86lc1HxqnHquM865c4gtYuveJ8R2BVFyQuAmAogtYutcNaf8pHKpQuiOU/tNnavWp8Q5dw6xRWzd+4TYriBKTgjcRACxRWydq6ZITXuMWxzVfCoXNZ8ap57rjHPuHGKL2Lr3CbFdQZScELiJAGKL2DpXzSk/qVyqELrj1H5T56r1KXHOnUNsEVv3PiG2K4iSEwIbElBeaCtiNkRFycUEVuxoIqdbgNWRJXpVz1R7aI9T+yXu6+tbBups+f88ppIiDgIHE0g9RA9GSmsBAqk9dp+L2M5LTWDtho5078qT8qmgEVuVFHEQOJhA6uF4MFJaCxBI7bH7XMQWsXXv1An51EcKYquSIg4CBxNIPfQORkprAQKpPXafi9gitu6dOiGf+khBbFVSxEHgYAKph97BSGktQCC1x+5zEVvE1r1TJ+RTHymIrUqKOAgcTCD10DsYKa0FCKT22H0uYovYunfqhHzqIwWxVUkRB4GDCaQeegcjpbUAgdQeu89FbBFb906dkE99pCC2KiniIHAwgdRD72CktBYgkNpj97mILWLr3qkT8qmPFMRWJUUcBA4mkHroHYyU1gIEUnvsPhexRWzdO3VCPvWRgtiqpIiDwMEEUg+9g5HSWoBAao/d5yK2iK17p07Ipz5SEFuVFHEQOJhA6qF3MFJaCxBI7bH7XMQWsXXv1An51EcKYquSIg4CBxNIPfQORkprAQKpPXafi9gitu6dOiGf+khBbFVSxEHgYAKph97BSGktQCC1x+5zEVvE1r1TJ+RTHymIrUqKOAgcTCD10DsYKa0FCKT22H0uYovYunfqhHzqIyUqtv/93/6fl/JHbYY4CEAAAhCAwO4EUhKyOzfq7yKQ2mPEtmsPqAYCEIAABB5OICUED8dO+2YCqT1GbM2DJB0EIAABCEDgCoGUEFypmWsh8C2B1B4jtuwiBCAAAQhAoIhASgiKEFDKAQRSe4zYHrA8tAABCEAAAucQSAnBOQTppIFAao8R24bpUwMEIAABCEDgLwRSQsAAIOAkkNpjxNY5RXJBAAIQgAAELhJICcHFsrkcAr8hkNpjxJZFhAAEIAABCBQRSAlBEQJKOYBAao8R2wOWhxYgAAEIQOAcAikhOIcgnTQQSO0xYtswfWqAAAQgAAEI/IVASggYAAScBFJ7jNg6p0guCEAAAhCAwEUCKSG4WDaXQ+A3BFJ7jNiyiBCAAAQgAIEiAikhKEJAKQcQSO0xYnvA8tACBCAAAQicQyAlBOcQpJMGAqk9Rmwbpk8NEIAABCAAgb8QSAkBA4CAk0Bqj6Ni6wT4tFz//v/975fy52lc6HeOQOoBxLlfX6cy+B//9W9eyp9T+9+xr7mnB1dBoIsAYts1D7kaRWrfMfxAQCGw40uYmrulWJHadwxz7Jmj8qwgBgLtBBDb9gn9oD7EdtPBlZaNXPTIxSmzQGz326nSxxNlQWCIAGI7hKsnGLHtmcUJlZwiU/TRI1OIbc8s1PvihGcZPUAAsd10BxDbTQdXWrb64iNuP1lJzQyx3W9XSh9PlAWBIQKI7RCunmDEtmcWJ1SSkh/O3U9+1JkhtvvN9oRnGT1AALHddAcQ200HV1q2KivE7ScrqZkhtvvtSunjibIgMEQAsR3C1ROM2PbM4oRKUvLDufvJjzozxHa/2Z7wLKMHCCC2m+4AYrvp4ErLVmWFuP1kJTUzxHa/XSl9PFEWBIYIILZDuHqCEdueWZxQSUp+OHc/+VFnhtjuN9sTnmX0AAHEdtMdQGw3HVxp2aqsELefrKRmhtjutyuljyfKgsAQAcR2CFdPMGLbM4sTKknJD+fuJz/qzBDb/WZ7wrOMHiCA2G66A4jtpoMrLVuVFeL2k5XUzBDb/Xal9PFEWRAYIoDYDuHqCUZse2ZxQiUp+eHc/eRHnRliu99sT3iW0QMEPhXbz/6P/N8+XjCAATvADrAD7AA7wA6wA3vtwBcGttfAmBfzYgfYAXaAHWAH2AF24PMdQGw/uDm4OdgBdoAdYAfYAXaAHThhBxBbxJZfu2AH2AF2gB1gB9gBduCIHUBsWeQjFvmEv2XSA19L2AF2gB1gB9iBazuA2CK2iC07wA6wA+wAO8AOsANH7ABiyyIfscj8Dffa33DhBz92gB1gB9iBE3YAsUVsEVt2gB1gB9gBdoAdYAeO2AHElkU+YpFP+FsmPfC1hB1gB9gBdoAduLYDiC1ii9iyA+wAO8AOsAPsADtwxA4gtizyEYvM33Cv/Q0XfvBjB9gBdoAdOGEHEFvEFrFlB9gBdoAdYAfYAXbgiB1AbFnkIxb5hL9l0gNfS9gBdoAdYAfYgWs78P8BU0IcgNlb/EEAAAAASUVORK5CYII='


@app.route.view('base_test')
class ATestView(BaseView):
    @app.route.interface('GET')
    async def captcha(self):
        self.finish_raw(base64.b64decode(captcha), 206, content_type='image/png')


async def test_get_captcha():
    request = make_mocked_request('GET', '/api/base_test')
    view = ATestView(app, request)
    await view._prepare()
    await view.captcha()
    assert view.ret_val == base64.b64decode(captcha)
    assert view.response.content_type == 'image/png'
    assert view.response.status == 206


@app.route.view('base')
class FinishTestView(BaseView):
    @app.route.get()
    async def test(self):
        self.finish_raw(b'body', 200)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aaa = 1

    def on_finish(self):
        self.aaa = 2


async def test_on_finish():
    req = make_mocked_request('GET', '/api/base/test')

    async def send(message):
        pass

    view = await app(req.scope, req.receive, send, raise_for_resp=True)
    assert view.aaa == 2


app.prepare()
