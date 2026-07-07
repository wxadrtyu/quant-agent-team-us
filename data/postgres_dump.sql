--
-- PostgreSQL database dump
--

\restrict OcOdhJf3TjRkBGcdHcsut13QdBbuEA89KOFkdG7ZvGSK7BOrfgywgbNwFztst5k

-- Dumped from database version 17.9 (Homebrew)
-- Dumped by pg_dump version 17.9 (Homebrew)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

DROP DATABASE postgres;
--
-- Name: postgres; Type: DATABASE; Schema: -; Owner: laisicong
--

CREATE DATABASE postgres WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'en_US.UTF-8';


ALTER DATABASE postgres OWNER TO laisicong;

\unrestrict OcOdhJf3TjRkBGcdHcsut13QdBbuEA89KOFkdG7ZvGSK7BOrfgywgbNwFztst5k
\connect postgres
\restrict OcOdhJf3TjRkBGcdHcsut13QdBbuEA89KOFkdG7ZvGSK7BOrfgywgbNwFztst5k

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: DATABASE postgres; Type: COMMENT; Schema: -; Owner: laisicong
--

COMMENT ON DATABASE postgres IS 'default administrative connection database';


--
-- PostgreSQL database dump complete
--

\unrestrict OcOdhJf3TjRkBGcdHcsut13QdBbuEA89KOFkdG7ZvGSK7BOrfgywgbNwFztst5k

